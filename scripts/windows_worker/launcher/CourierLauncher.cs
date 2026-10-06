using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.IO;
using System.Threading;
using System.Net;

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

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        static extern int MessageBox(IntPtr hWnd, string text, string caption, uint type);

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
        
        static object logLock = new object();
        
        static Process StartComponent(IntPtr hJob, string pythonExe, string baseDir, string logDir, string name, string args, string logFile) {
            var psi = new ProcessStartInfo {
                FileName = pythonExe,
                Arguments = args,
                UseShellExecute = false,
                WorkingDirectory = baseDir,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };
            Process p = new Process();
            p.StartInfo = psi;
            
            DataReceivedEventHandler logHandler = (s, e) => {
                if (e.Data != null) {
                    lock(logLock) {
                        File.AppendAllText(Path.Combine(logDir, logFile), string.Format("[{0:O}] {1}{2}", DateTime.UtcNow, e.Data, Environment.NewLine));
                    }
                }
            };
            
            p.OutputDataReceived += logHandler;
            p.ErrorDataReceived += logHandler;
            p.Start();
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();
            if (hJob != IntPtr.Zero) {
                AssignProcessToJobObject(hJob, p.Handle);
            }
            return p;
        }

        static void Main(string[] args)
        {
            SetConsoleCtrlHandler(ConsoleCtrlCheck, true);

            IntPtr hJob = IntPtr.Zero;
            if (Environment.GetEnvironmentVariable("COURIER_TEST_NO_JOB") != "1")
            {
                hJob = CreateJobObject(IntPtr.Zero, null);
                if (hJob == IntPtr.Zero)
                {
                    MessageBox(IntPtr.Zero, "Failed to create Job Object.", "Courier Launcher Error", 0x10);
                    Environment.Exit(1);
                }

                var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

                int length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
                if (!SetInformationJobObject(hJob, JobObjectExtendedLimitInformation, ref info, length))
                {
                    MessageBox(IntPtr.Zero, "Failed to set Job Object limits.", "Courier Launcher Error", 0x10);
                    Environment.Exit(1);
                }
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string dataDir = Environment.ExpandEnvironmentVariables(@"%LOCALAPPDATA%\Courier");
            
            string oldDataDir = Environment.ExpandEnvironmentVariables(@"%PROGRAMDATA%\CourierWorker");
            string oldConfigPath = Path.Combine(oldDataDir, "config.json");
            string configPath = Path.Combine(dataDir, "config.json");
            string logDir = Path.Combine(dataDir, "logs");
            
            int cp = 8765;
            int hp = 8766;
            string workerId = "";
            
            if (File.Exists(oldConfigPath)) {
                string json = File.ReadAllText(oldConfigPath);
                System.Text.RegularExpressions.Match workerMatch = System.Text.RegularExpressions.Regex.Match(json, "\"COURIER_WORKER_ID\"\\s*:\\s*\"([^\"]+)\"");
                if (workerMatch.Success) workerId = workerMatch.Groups[1].Value;
            }

            if (File.Exists(configPath))
            {
                string json = File.ReadAllText(configPath);
                System.Text.RegularExpressions.Match cpMatch = System.Text.RegularExpressions.Regex.Match(json, "\"COURIER_CONTROLLER_PORT\"\\s*:\\s*(\\d+)");
                if (cpMatch.Success) int.TryParse(cpMatch.Groups[1].Value, out cp);
                
                System.Text.RegularExpressions.Match hpMatch = System.Text.RegularExpressions.Regex.Match(json, "\"COURIER_HUB_PORT\"\\s*:\\s*(\\d+)");
                if (hpMatch.Success) int.TryParse(hpMatch.Groups[1].Value, out hp);
                
                System.Text.RegularExpressions.Match workerMatch = System.Text.RegularExpressions.Regex.Match(json, "\"COURIER_WORKER_ID\"\\s*:\\s*\"([^\"]+)\"");
                if (workerMatch.Success) workerId = workerMatch.Groups[1].Value;
            }

            string tokenPath = Path.Combine(dataDir, @"run\controller.token");
            string token = "";
            if (File.Exists(tokenPath))
            {
                token = File.ReadAllText(tokenPath).Trim();
            }

            bool alreadyRunning = false;
            if (!string.IsNullOrEmpty(token))
            {
                try {
                    var req = (HttpWebRequest)WebRequest.Create(string.Format("http://127.0.0.1:{0}/v1/health", cp));
                    req.Headers.Add("X-Courier-Token", token);
                    req.Timeout = 2000;
                    using (var res = (HttpWebResponse)req.GetResponse()) {
                        if (res.StatusCode == HttpStatusCode.OK) alreadyRunning = true;
                    }
                } catch { }
            }

            if (alreadyRunning)
            {
                ProcessStartInfo psi = new ProcessStartInfo(string.Format("http://127.0.0.1:{0}/", hp));
                psi.UseShellExecute = true;
                Process.Start(psi);
                return;
            }

            string pythonExe = "uv";
            if (File.Exists(Path.Combine(baseDir, "python", "python.exe"))) {
                pythonExe = Path.Combine(baseDir, "python", "python.exe");
            }
            
            if (!Directory.Exists(logDir)) Directory.CreateDirectory(logDir);
            
            string ctrlArgs = string.Format("run python -m courier_core.serve --home \"{0}\" --port {1}", dataDir, cp);
            string workerArgs = string.Format("run python -m courier_worker.host --home \"{0}\" --controller http://127.0.0.1:{1} --max-tasks 1 --heartbeat 2", dataDir, cp);
            if (!string.IsNullOrEmpty(workerId)) {
                workerArgs += string.Format(" --worker-id \"{0}\"", workerId);
            }
            string hubArgs = string.Format("run python -m courier_hub --home \"{0}\" --controller http://127.0.0.1:{1} --port {2}", dataDir, cp, hp);
            
            if (pythonExe != "uv") {
                ctrlArgs = string.Format("-m courier_core.serve --home \"{0}\" --port {1}", dataDir, cp);
                workerArgs = string.Format("-m courier_worker.host --home \"{0}\" --controller http://127.0.0.1:{1} --max-tasks 1 --heartbeat 2", dataDir, cp);
                if (!string.IsNullOrEmpty(workerId)) {
                    workerArgs += string.Format(" --worker-id \"{0}\"", workerId);
                }
                hubArgs = string.Format("-m courier_hub --home \"{0}\" --controller http://127.0.0.1:{1} --port {2}", dataDir, cp, hp);
            }

            try
            {
                var pCtrl = StartComponent(hJob, pythonExe, baseDir, logDir, "controller", ctrlArgs, "controller.log");
                
                bool healthOk = false;
                for (int i = 0; i < 30; i++) {
                    Thread.Sleep(500);
                    if (pCtrl.HasExited) break;
                    
                    if (File.Exists(tokenPath)) {
                        string t = File.ReadAllText(tokenPath).Trim();
                        try {
                            var req = (HttpWebRequest)WebRequest.Create(string.Format("http://127.0.0.1:{0}/v1/health", cp));
                            req.Headers.Add("X-Courier-Token", t);
                            req.Timeout = 1000;
                            using (var res = (HttpWebResponse)req.GetResponse()) {
                                if (res.StatusCode == HttpStatusCode.OK) {
                                    healthOk = true;
                                    break;
                                }
                            }
                        } catch { }
                    }
                }

                if (!healthOk) {
                    string msg = "Controller failed to start or become healthy.\nCheck logs at: " + logDir;
                    File.WriteAllText(Path.Combine(dataDir, "crash.txt"), msg);
                    MessageBox(IntPtr.Zero, msg, "Courier Launcher Error", 0x10);
                    return;
                }

                var pWorker = StartComponent(hJob, pythonExe, baseDir, logDir, "worker", workerArgs, "worker.log");
                var pHub = StartComponent(hJob, pythonExe, baseDir, logDir, "hub", hubArgs, "hub.log");

                ProcessStartInfo pBrowser = new ProcessStartInfo(string.Format("http://127.0.0.1:{0}/", hp));
                pBrowser.UseShellExecute = true;
                Process.Start(pBrowser);

                while (true)
                {
                    Thread.Sleep(5000);
                    if (pCtrl.HasExited) pCtrl = StartComponent(hJob, pythonExe, baseDir, logDir, "controller", ctrlArgs, "controller.log");
                    if (pWorker.HasExited) pWorker = StartComponent(hJob, pythonExe, baseDir, logDir, "worker", workerArgs, "worker.log");
                    if (pHub.HasExited) pHub = StartComponent(hJob, pythonExe, baseDir, logDir, "hub", hubArgs, "hub.log");
                }
            }
            catch (Exception ex)
            {
                string msg = "Error launching daemon: " + ex.Message + "\nCheck logs at: " + logDir;
                File.WriteAllText(Path.Combine(dataDir, "crash.txt"), "Error launching daemon: " + ex.ToString());
                MessageBox(IntPtr.Zero, msg, "Courier Launcher Error", 0x10);
            }
        }
    }
}
