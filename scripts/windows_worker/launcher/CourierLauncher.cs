using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.IO;

namespace CourierLauncher
{
    class Program
    {
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
            // Ignore events to let the python child process handle them
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
            SetConsoleCtrlHandler(ConsoleCtrlCheck, true);

            IntPtr hJob = CreateJobObject(IntPtr.Zero, null);
            if (hJob == IntPtr.Zero)
            {
                Console.WriteLine("Failed to create Job Object.");
                Environment.Exit(1);
            }

            var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

            int length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            if (!SetInformationJobObject(hJob, JobObjectExtendedLimitInformation, ref info, length))
            {
                Console.WriteLine("Failed to set Job Object limits.");
                Environment.Exit(1);
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string workerModule = "courier_worker.host";
            
            string dataDir = Environment.ExpandEnvironmentVariables(@"%PROGRAMDATA%\CourierWorker");
            string configPath = Path.Combine(dataDir, "config.json");
            string logDir = Path.Combine(dataDir, "logs");
            string logPath = Path.Combine(logDir, "host.log");
            string serverUrl = "";
            string workerId = "";
            
            if (File.Exists(configPath))
            {
                string json = File.ReadAllText(configPath);
                string[] lines = json.Split(new[] { ',', '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries);
                foreach (string line in lines)
                {
                    if (line.Contains("\"COURIER_SERVER\""))
                    {
                        int start = line.IndexOf(":", StringComparison.Ordinal) + 1;
                        serverUrl = line.Substring(start).Trim(' ', '"');
                    }
                    else if (line.Contains("\"COURIER_WORKER_ID\""))
                    {
                        int start = line.IndexOf(":", StringComparison.Ordinal) + 1;
                        workerId = line.Substring(start).Trim(' ', '"');
                    }
                }
            }

            // Path priorities:
            // 1. Packaged embedded python (no external dependencies)
            // 2. uv fallback for dev environments
            string pythonExe = "uv";
            string arguments = string.Format("run python -m {0} --home \"{1}\" --controller \"{2}\" --worker-id \"{3}\"", workerModule, dataDir, serverUrl, workerId);
            
            if (File.Exists(Path.Combine(baseDir, "python", "python.exe"))) {
                pythonExe = Path.Combine(baseDir, "python", "python.exe");
                arguments = string.Format("-m {0} --home \"{1}\" --controller \"{2}\" --worker-id \"{3}\"", workerModule, dataDir, serverUrl, workerId);
            }
            
            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = arguments,
                UseShellExecute = false,
                WorkingDirectory = baseDir,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };
            
            try
            {
                if (!Directory.Exists(logDir))
                {
                    Directory.CreateDirectory(logDir);
                }

                Process proc = new Process();
                proc.StartInfo = psi;

                object logLock = new object();
                
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

                if (proc == null)
                {
                    Console.WriteLine("Failed to start process.");
                    Environment.Exit(1);
                }

                if (!AssignProcessToJobObject(hJob, proc.Handle))
                {
                    Console.WriteLine("Failed to assign process to Job Object. Warning: Orphans possible.");
                }

                proc.WaitForExit();
                Environment.Exit(proc.ExitCode);
            }
            catch (Exception ex)
            {
                File.WriteAllText("crash.txt", "Error launching daemon: " + ex.ToString());
                Console.WriteLine("Error launching daemon: " + ex.Message);
                Environment.Exit(1);
            }
        }
    }
}
