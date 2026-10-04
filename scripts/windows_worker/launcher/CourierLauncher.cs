using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Security.Principal;

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

        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        static extern uint SetThreadExecutionState(uint esFlags);
        
        const uint ES_CONTINUOUS = 0x80000000;
        const uint ES_SYSTEM_REQUIRED = 0x00000001;

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
            try
            {
                using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
                {
                    WindowsPrincipal principal = new WindowsPrincipal(identity);
                    // if (principal.IsInRole(WindowsBuiltInRole.Administrator))
                    // {
                    //     Environment.Exit(3);
                    // }
                    // if (identity.IsSystem)
                    // {
                    //     Environment.Exit(3);
                    // }
                }

                string customHome = null;
                bool isStop = false;
                bool isStatus = false;
                for (int i = 0; i < args.Length; i++)
                {
                    if (args[i] == "--home" && i + 1 < args.Length)
                    {
                        customHome = args[i + 1];
                        i++;
                    }
                    else if (args[i] == "--stop") isStop = true;
                    else if (args[i] == "--status") isStatus = true;
                }


            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            
            // Check for v1 remote worker mode config
            string v1DataDir = Environment.ExpandEnvironmentVariables(@"%PROGRAMDATA%\CourierWorker");
            string v1ConfigPath = Path.Combine(v1DataDir, "config.json");
            string externalServerUrl = "";
            string workerId = "";
            bool isRemoteMode = false;
            
            if (File.Exists(v1ConfigPath))
            {
                string json = File.ReadAllText(v1ConfigPath);
                System.Text.RegularExpressions.Match serverMatch = System.Text.RegularExpressions.Regex.Match(json, "\"COURIER_SERVER\"\\s*:\\s*\"([^\"]+)\"");
                if (serverMatch.Success) {
                    externalServerUrl = serverMatch.Groups[1].Value;
                    isRemoteMode = true;
                }
                
                System.Text.RegularExpressions.Match workerMatch = System.Text.RegularExpressions.Regex.Match(json, "\"COURIER_WORKER_ID\"\\s*:\\s*\"([^\"]+)\"");
                if (workerMatch.Success) {
                    workerId = workerMatch.Groups[1].Value;
                }
            }

            string homeDir;
            if (!string.IsNullOrEmpty(customHome))
            {
                homeDir = Path.GetFullPath(customHome);
            }
            else if (isRemoteMode)
            {
                homeDir = v1DataDir;
            }
            else
            {
                homeDir = Environment.ExpandEnvironmentVariables(@"%LOCALAPPDATA%\Courier");
            }

            string runDirEarly = Path.Combine(homeDir, "run");
            if (!Directory.Exists(runDirEarly))
            {
                Directory.CreateDirectory(runDirEarly);
            }
            string pidFile = Path.Combine(runDirEarly, "launcher.pid");

            if (isStop)
            {
                if (File.Exists(pidFile))
                {
                    string pidStr = File.ReadAllText(pidFile).Trim();
                    int pid;
                    if (int.TryParse(pidStr, out pid))
                    {
                        try
                        {
                            Process p = Process.GetProcessById(pid);
                            p.Kill();
                            Console.WriteLine("Stopped Courier.");
                        }
                        catch
                        {
                            Console.WriteLine("Process not running.");
                        }
                    }
                    File.Delete(pidFile);
                }
                else
                {
                    Console.WriteLine("PID file not found.");
                }
                return;
            }
            
            if (isStatus)
            {
                if (File.Exists(pidFile))
                {
                    string pidStr = File.ReadAllText(pidFile).Trim();
                    int pid;
                    if (int.TryParse(pidStr, out pid))
                    {
                        try
                        {
                            Process p = Process.GetProcessById(pid);
                            Console.WriteLine("Status: RUNNING (PID: " + pid + ")");
                            return;
                        }
                        catch
                        {
                        }
                    }
                }
                Console.WriteLine("Status: STOPPED");
                return;
            }

            string mutexName = "Global\\CourierAppMutex_" + homeDir.Replace("\\", "_").Replace(":", "_").ToLowerInvariant();
            IntPtr mutex = CreateMutex(IntPtr.Zero, true, mutexName);
            if (mutex == IntPtr.Zero)
            {
                Console.WriteLine("FATAL: Could not create single-instance mutex.");
                Environment.Exit(1);
            }
            if (GetLastError() == ERROR_ALREADY_EXISTS)
            {
                Console.WriteLine("Duplicate instance detected for this home directory. Exiting.");
                Environment.Exit(2);
            }

            File.WriteAllText(pidFile, Process.GetCurrentProcess().Id.ToString());

            SetConsoleCtrlHandler(ConsoleCtrlCheck, true);

            IntPtr hJob = CreateJobObject(IntPtr.Zero, null);
            if (hJob == IntPtr.Zero)
            {
                Environment.Exit(1);
            }

            var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | 0x0100; // 0x0100 is JOB_OBJECT_LIMIT_PROCESS_MEMORY
            info.ProcessMemoryLimit = new UIntPtr(1024L * 1024 * 1024); // 1 GB memory limit per process

            int length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            if (!SetInformationJobObject(hJob, JobObjectExtendedLimitInformation, ref info, length))
            {
                Environment.Exit(1);
            }

            string logDir = Path.Combine(homeDir, "logs");
            if (!Directory.Exists(logDir))
            {
                Directory.CreateDirectory(logDir);
            }

            int cp = 0; // Controller port
            string controllerUrl = isRemoteMode ? externalServerUrl : "";
            
            string runDir = Path.Combine(homeDir, "run");
            if (!Directory.Exists(runDir))
            {
                Directory.CreateDirectory(runDir);
            }

            string tokenPath = Path.Combine(runDir, "controller.token");
            string apiKey = Environment.GetEnvironmentVariable("COURIER_API_KEY");
            string verifierKey = Environment.GetEnvironmentVariable("COURIER_VERIFIER_API_KEY");

            if (!isRemoteMode)
            {
                if (string.IsNullOrEmpty(apiKey) && File.Exists(tokenPath))
                {
                    apiKey = File.ReadAllText(tokenPath).Trim();
                }
                
                if (string.IsNullOrEmpty(apiKey))
                {
                    apiKey = Guid.NewGuid().ToString("N") + Guid.NewGuid().ToString("N");
                    File.WriteAllText(tokenPath, apiKey);
                }
                else if (!File.Exists(tokenPath))
                {
                    File.WriteAllText(tokenPath, apiKey);
                }

                if (string.IsNullOrEmpty(verifierKey))
                {
                    verifierKey = Guid.NewGuid().ToString("N") + Guid.NewGuid().ToString("N");
                }
            }

            // Strict bundled Python requirement
            string pythonExe = Path.Combine(baseDir, "python", "python.exe");
            if (!File.Exists(pythonExe))
            {
                File.AppendAllText(Path.Combine(logDir, "launcher.log"), "FATAL: Bundled Python not found at " + pythonExe + ". UV fallback is strictly prohibited.\n");
                Environment.Exit(1);
            }

            Func<string, string, string, Action<string>, Process> StartPythonProcess = (module, arguments, logName, onOutputLine) =>
            {
                string fullArgs = string.Format("-m {0} {1}", module, arguments);
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
                psi.EnvironmentVariables["COURIER_API_KEY"] = apiKey;
                psi.EnvironmentVariables["COURIER_VERIFIER_API_KEY"] = verifierKey;


                Process proc = new Process();
                proc.StartInfo = psi;

                object logLock = new object();
                string logPath = Path.Combine(logDir, logName);
                
                DataReceivedEventHandler logHandler = (sender, e) => {
                    if (e.Data != null) {
                        if (onOutputLine != null) { onOutputLine(e.Data); }
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
                    File.AppendAllText(logPath, "FATAL: Failed to assign process to Job Object. Terminating uncontained process.\n");
                    try { proc.Kill(); } catch { }
                    throw new Exception("Failed to assign process to Job Object (Containment failure)");
                }
                
                return proc;
            };

            Process controllerProc = null;

            if (!isRemoteMode)
            {
                // 1. Start Controller (Local Mode Only)
                string controllerArgs = string.Format("--home \"{0}\" --port 0 --print-port", homeDir);
                controllerProc = StartPythonProcess("courier_core.serve", controllerArgs, "controller.log", (line) => {
                    int port;
                    if (cp == 0 && int.TryParse(line.Trim(), out port)) {
                        cp = port;
                        controllerUrl = string.Format("http://127.0.0.1:{0}", cp);
                    }
                });

                // Wait for health check with a strict 10 second timeout
                string startupState = "STARTING";
                File.AppendAllText(Path.Combine(logDir, "launcher.log"), "Controller state: STARTING\n");

                Stopwatch sw = Stopwatch.StartNew();
                while (sw.Elapsed.TotalSeconds < 10)
                {
                    if (controllerProc != null && controllerProc.HasExited) 
                    { 
                        startupState = "FAILED"; 
                        break; 
                    }
                    if (cp == 0 || string.IsNullOrEmpty(controllerUrl))
                    {
                        Thread.Sleep(200);
                        continue;
                    }
                    try { 
                        var request = System.Net.WebRequest.Create(string.Format("{0}/v1/health", controllerUrl));
                        request.Timeout = 1000;
                        string controllerTokenPath = Path.Combine(homeDir, "run", "controller.token");
                        string controllerLocalToken = File.Exists(controllerTokenPath) ? File.ReadAllText(controllerTokenPath).Trim() : "";
                        request.Headers.Add("X-Courier-Token", controllerLocalToken);
                        using (var response = request.GetResponse())
                        {
                            using (var reader = new System.IO.StreamReader(response.GetResponseStream()))
                            {
                                string content = reader.ReadToEnd();
                                if (content.Contains("\"mode\""))
                                {
                                    startupState = "READY";
                                    break;
                                }
                            }
                        }
                    }
                    catch (Exception ex) { 
                        File.AppendAllText(Path.Combine(logDir, "launcher.log"), "Ping failed: " + ex.Message + "\n");
                    }
                    Thread.Sleep(200);
                }
                sw.Stop();
                
                if (startupState == "STARTING")
                {
                    startupState = "TIMEOUT";
                }

                File.AppendAllText(Path.Combine(logDir, "launcher.log"), "Controller state: " + startupState + "\n");

                if (startupState != "READY")
                {
                    Environment.Exit(1);
                }
            }

            // Helper for Crash Backoff
            Action<Func<Process>, string> MonitorProcess = (startFunc, name) =>
            {
                new Thread(() => {
                    int initialBackoff = 2000;
                    int backoff = initialBackoff;
                    int maxBackoff = 300000;
                    TimeSpan healthyUptimeThreshold = TimeSpan.FromMinutes(2);

                    while (true)
                    {
                        try
                        {
                            DateTime startTime = DateTime.UtcNow;
                            Process p = startFunc();
                            p.WaitForExit();
                            
                            if (DateTime.UtcNow - startTime > healthyUptimeThreshold)
                            {
                                backoff = initialBackoff;
                            }

                            File.AppendAllText(Path.Combine(logDir, "launcher.log"), string.Format("[{0:O}] {1} exited with code {2}. Restarting in {3}ms...\n", DateTime.UtcNow, name, p.ExitCode, backoff));
                        }
                        catch (Exception ex)
                        {
                            File.AppendAllText(Path.Combine(logDir, "launcher.log"), string.Format("[{0:O}] {1} failed to start: {2}. Restarting in {3}ms...\n", DateTime.UtcNow, name, ex.Message, backoff));
                        }

                        Thread.Sleep(backoff);
                        backoff = Math.Min(maxBackoff, backoff * 2);
                    }
                }) { IsBackground = true }.Start();
            };

            // 2. Start Worker with backoff (Both Modes)
            MonitorProcess(() => {
                string wArgs = string.Format("--home \"{0}\" --controller \"{1}\" --max-tasks 1 --heartbeat 2", homeDir, controllerUrl);
                if (!string.IsNullOrEmpty(workerId)) {
                    wArgs += string.Format(" --worker-id \"{0}\"", workerId);
                }
                return StartPythonProcess("courier_worker.host", wArgs, "worker.log", null);
            }, "Worker");

            if (!isRemoteMode)
            {
                // Wait for controller. Controller crash will restart the whole suite since we exit.
                int initialControllerBackoff = 2000;
                int controllerBackoff = initialControllerBackoff;
                TimeSpan healthyControllerUptimeThreshold = TimeSpan.FromMinutes(2);
                DateTime controllerStartTime = DateTime.UtcNow;

                while (true)
                {
                    if (controllerProc != null)
                    {
                        while (!controllerProc.HasExited)
                        {
                            Thread.Sleep(5000);
                            if (cp == 0 || string.IsNullOrEmpty(controllerUrl)) continue;
                            try {
                                var request = System.Net.WebRequest.Create(string.Format("{0}/v1/health", controllerUrl));
                                request.Timeout = 2000;
                                string controllerTokenPath2 = Path.Combine(homeDir, "run", "controller.token");
                                string controllerLocalToken2 = File.Exists(controllerTokenPath2) ? File.ReadAllText(controllerTokenPath2).Trim() : "";
                                request.Headers.Add("X-Courier-Token", controllerLocalToken2);
                                using (var response = request.GetResponse()) {}
                            } catch {
                                File.AppendAllText(Path.Combine(logDir, "launcher.log"), string.Format("[{0:O}] Controller liveness check failed. Terminating process.\n", DateTime.UtcNow));
                                try { controllerProc.Kill(); } catch { }
                                break;
                            }
                        }
                        
                        if (DateTime.UtcNow - controllerStartTime > healthyControllerUptimeThreshold)
                        {
                            controllerBackoff = initialControllerBackoff;
                        }

                        File.AppendAllText(Path.Combine(logDir, "launcher.log"), string.Format("[{0:O}] Controller exited with code {1}. Restarting in {2}ms...\n", DateTime.UtcNow, controllerProc.ExitCode, controllerBackoff));
                    }
                    
                    Thread.Sleep(controllerBackoff);
                    controllerBackoff = Math.Min(300000, controllerBackoff * 2);
                    
                    try
                    {
                        cp = 0;
                        string controllerArgs = string.Format("--home \"{0}\" --port 0 --print-port", homeDir);
                        controllerProc = StartPythonProcess("courier_core.serve", controllerArgs, "controller.log", (line) => {
                            int port;
                            if (cp == 0 && int.TryParse(line.Trim(), out port)) {
                                cp = port;
                                controllerUrl = string.Format("http://127.0.0.1:{0}", cp);
                            }
                        });
                        controllerStartTime = DateTime.UtcNow;
                    }
                    catch (Exception ex)
                    {
                        File.AppendAllText(Path.Combine(logDir, "launcher.log"), string.Format("[{0:O}] Controller failed to start: {1}. Restarting in {2}ms...\n", DateTime.UtcNow, ex.Message, controllerBackoff));
                        controllerProc = null;
                    }
                }
            }
            else
            {
                // Remote mode: keep the main thread alive for the worker process
                while (true) {
                    Thread.Sleep(10000);
                }
            }
            }
            catch (Exception ex)
            {
                File.WriteAllText(Path.Combine(Environment.GetEnvironmentVariable("TEMP"), "courier_crash.log"), ex.ToString());
                Environment.Exit(5);
            }
        }
    }
}


