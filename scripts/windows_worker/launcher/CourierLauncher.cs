using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

namespace CourierLauncher
{
    class Program
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr CreateMutex(IntPtr lpMutexAttributes, bool bInitialOwner, string lpName);

        [DllImport("kernel32.dll")]
        static extern int GetLastError();

        const int ERROR_ALREADY_EXISTS = 183;

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        static extern IntPtr CreateJobObject(IntPtr a, string lpName);

        [DllImport("kernel32.dll")]
        static extern bool SetInformationJobObject(IntPtr hJob, int infoClass, ref JOBOBJECT_EXTENDED_LIMIT_INFORMATION lpJobObjectInfo, int cbJobObjectInfoLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

        [DllImport("kernel32.dll")]
        static extern bool SetConsoleCtrlHandler(ConsoleCtrlDelegate HandlerRoutine, bool Add);

        delegate bool ConsoleCtrlDelegate(uint CtrlType);

        static bool ConsoleCtrlCheck(uint ctrlType)
        {
            return true;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public Int64 PerProcessUserTimeLimit;
            public Int64 PerJobUserTimeLimit;
            public UInt32 LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public UInt32 ActiveProcessLimit;
            public UIntPtr Affinity;
            public UInt32 PriorityClass;
            public UInt32 SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct IO_COUNTERS
        {
            public UInt64 ReadOperationCount;
            public UInt64 WriteOperationCount;
            public UInt64 OtherOperationCount;
            public UInt64 ReadTransferCount;
            public UInt64 WriteTransferCount;
            public UInt64 OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryUsed;
            public UIntPtr PeakJobMemoryUsed;
        }

        const int JobObjectExtendedLimitInformation = 9;
        const UInt32 JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;

        static void Main(string[] args)
        {
            IntPtr mutex = CreateMutex(IntPtr.Zero, true, "Global\\CourierAppMutex_L6");
            if (GetLastError() == ERROR_ALREADY_EXISTS)
            {
                Environment.Exit(0);
            }

            SetConsoleCtrlHandler(ConsoleCtrlCheck, true);

            IntPtr hJob = CreateJobObject(IntPtr.Zero, null);
            if (hJob == IntPtr.Zero)
            {
                Environment.Exit(1);
            }

            var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

            int length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            if (!SetInformationJobObject(hJob, JobObjectExtendedLimitInformation, ref info, length))
            {
                Environment.Exit(1);
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            
            string homeDir;
            if (Environment.UserName.Equals("SYSTEM", StringComparison.OrdinalIgnoreCase))
            {
                homeDir = Path.Combine(Environment.GetEnvironmentVariable("ProgramData") ?? @"C:\ProgramData", "Courier");
            }
            else
            {
                homeDir = Environment.ExpandEnvironmentVariables(@"%LOCALAPPDATA%\Courier");
            }

            string logDir = Path.Combine(homeDir, "logs");
            
            if (!Directory.Exists(logDir))
            {
                Directory.CreateDirectory(logDir);
            }

            int cp = 8765;
            int hp = 8766;
            string controllerUrl = $"http://127.0.0.1:{cp}";
            string hubUrl = $"http://127.0.0.1:{hp}/";

            string pythonExe = "uv";
            bool isUv = true;
            if (File.Exists(Path.Combine(baseDir, "python", "python.exe"))) {
                pythonExe = Path.Combine(baseDir, "python", "python.exe");
                isUv = false;
            }

            Process StartPythonProcess(string module, string arguments, string logName)
            {
                string fullArgs = isUv ? $"run python -m {module} {arguments}" : $"-m {module} {arguments}";
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = fullArgs,
                    UseShellExecute = false,
                    WorkingDirectory = baseDir,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                };

                Process proc = new Process();
                proc.StartInfo = psi;

                object logLock = new object();
                string logPath = Path.Combine(logDir, logName);
                
                DataReceivedEventHandler logHandler = (sender, e) => {
                    if (e.Data != null) {
                        lock(logLock) {
                            File.AppendAllText(logPath, "[" + DateTime.UtcNow.ToString("O") + "] " + e.Data + Environment.NewLine);
                        }
                    }
                };

                proc.OutputDataReceived += logHandler;
                proc.ErrorDataReceived += logHandler;

                proc.Start();
                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();

                if (!AssignProcessToJobObject(hJob, proc.Handle))
                {
                    File.AppendAllText(Path.Combine(logDir, "launcher.log"), "Warning: Failed to assign process to Job Object.\n");
                }
                
                return proc;
            }

            // 1. Start Controller
            Process controllerProc = StartPythonProcess("courier_core.serve", $"--home \"{homeDir}\" --port {cp}", "controller.log");

            // Wait for health check
            using (HttpClient client = new HttpClient())
            {
                client.Timeout = TimeSpan.FromSeconds(2);
                bool healthy = false;
                for (int i = 0; i < 30; i++)
                {
                    try
                    {
                        var response = client.GetAsync($"{controllerUrl}/v1/health").Result;
                        if (response.IsSuccessStatusCode)
                        {
                            healthy = true;
                            break;
                        }
                    }
                    catch { }
                    Thread.Sleep(500);
                }
                
                if (!healthy)
                {
                    File.AppendAllText(Path.Combine(logDir, "launcher.log"), "Controller failed to start or become healthy.\n");
                    Environment.Exit(1);
                }
            }

            // Helper for Crash Backoff
            void MonitorProcess(Func<Process> startFunc, string name)
            {
                new Thread(() => {
                    int backoff = 2000;
                    int maxBackoff = 300000;
                    while (true)
                    {
                        Process p = startFunc();
                        p.WaitForExit();
                        File.AppendAllText(Path.Combine(logDir, "launcher.log"), $"[{DateTime.UtcNow:O}] {name} exited with code {p.ExitCode}. Restarting in {backoff}ms...\n");
                        Thread.Sleep(backoff);
                        backoff = Math.Min(maxBackoff, backoff * 2);
                    }
                }) { IsBackground = true }.Start();
            }

            // 2. Start Worker with backoff
            MonitorProcess(() => StartPythonProcess("courier_worker.host", $"--home \"{homeDir}\" --controller \"{controllerUrl}\" --max-tasks 1 --heartbeat 2", "worker.log"), "Worker");

            // 3. Start Hub with backoff
            MonitorProcess(() => StartPythonProcess("courier_hub", $"--home \"{homeDir}\" --controller \"{controllerUrl}\" --port {hp}", "hub.log"), "Hub");

            // 4. Open Browser
            try {
                Process.Start(new ProcessStartInfo(hubUrl) { UseShellExecute = true });
            } catch (Exception ex) {
                File.AppendAllText(Path.Combine(logDir, "launcher.log"), "Could not open browser: " + ex.Message + "\n");
            }

            // Wait for controller. Controller crash will restart the whole suite since we exit.
            int controllerBackoff = 2000;
            while (true)
            {
                controllerProc.WaitForExit();
                File.AppendAllText(Path.Combine(logDir, "launcher.log"), $"[{DateTime.UtcNow:O}] Controller exited with code {controllerProc.ExitCode}. Restarting in {controllerBackoff}ms...\n");
                Thread.Sleep(controllerBackoff);
                controllerBackoff = Math.Min(300000, controllerBackoff * 2);
                
                controllerProc = StartPythonProcess("courier_core.serve", $"--home \"{homeDir}\" --port {cp}", "controller.log");
            }
        }
    }
}
