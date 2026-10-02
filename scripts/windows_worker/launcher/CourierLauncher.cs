using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.IO;
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
            if (mutex == IntPtr.Zero)
            {
                Console.WriteLine("FATAL: Could not create single-instance mutex.");
                Environment.Exit(1);
            }
            if (GetLastError() == ERROR_ALREADY_EXISTS)
            {
                Console.WriteLine("Duplicate instance detected. Exiting.");
                Environment.Exit(2);
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
            if (isRemoteMode)
            {
                homeDir = v1DataDir;
            }
            else
            {
                if (Environment.UserName.Equals("SYSTEM", StringComparison.OrdinalIgnoreCase))
                {
                    homeDir = Path.Combine(Environment.GetEnvironmentVariable("ProgramData") ?? @"C:\ProgramData", "Courier");
                }
                else
                {
                    homeDir = Environment.ExpandEnvironmentVariables(@"%LOCALAPPDATA%\Courier");
                }
            }

            string logDir = Path.Combine(homeDir, "logs");
            if (!Directory.Exists(logDir))
            {
                Directory.CreateDirectory(logDir);
            }

            int cp = 8080; // Controller port (server.app defaults to 8080)
            int hp = 8081; // Hub port
            string controllerUrl = isRemoteMode ? externalServerUrl : string.Format("http://127.0.0.1:{0}", cp);
            string hubUrl = string.Format("http://127.0.0.1:{0}/", hp);

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

            Func<string, string, string, Process> StartPythonProcess = (module, arguments, logName) =>
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

                // Inject PORT for dashboard.server if it's the hub
                if (module == "dashboard.server")
                {
                    psi.EnvironmentVariables["PORT"] = hp.ToString();
                }
                // Inject state file and keys for server.app
                if (module == "server.app")
                {
                    psi.EnvironmentVariables["COURIER_STATE_FILE"] = Path.Combine(homeDir, "central_state.json");
                    if (!string.IsNullOrEmpty(apiKey)) psi.EnvironmentVariables["COURIER_API_KEY"] = apiKey;
                    if (!string.IsNullOrEmpty(verifierKey)) psi.EnvironmentVariables["COURIER_VERIFIER_API_KEY"] = verifierKey;
                }

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
                controllerProc = StartPythonProcess("server.app", "", "controller.log");

                // Wait for health check
                bool healthy = false;
                for (int i = 0; i < 30; i++)
                {
                    try { if (controllerProc != null && controllerProc.HasExited) { healthy = false; break; } var request = System.Net.WebRequest.Create(string.Format("{0}/health", controllerUrl));
                        request.Timeout = 2000;
                        using (var response = request.GetResponse())
                        using (var reader = new System.IO.StreamReader(response.GetResponseStream()))
                        {
                            string content = reader.ReadToEnd();
                            if (content.Contains("healthy") && content.Contains("courier-controller"))
                            {
                                healthy = true;
                                break;
                            }
                        }
                    }
                    catch { }
                    Thread.Sleep(500);
                }
                
                if (!healthy)
                {
                    File.AppendAllText(Path.Combine(logDir, "launcher.log"), "Controller failed to start or health identity check failed.\n");
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
            string workerArgs = string.Format("--home \"{0}\" --controller \"{1}\" --max-tasks 1 --heartbeat 2", homeDir, controllerUrl);
            if (!string.IsNullOrEmpty(workerId)) {
                workerArgs += string.Format(" --worker-id \"{0}\"", workerId);
            }
            MonitorProcess(() => StartPythonProcess("courier_worker.host", workerArgs, "worker.log"), "Worker");

            if (!isRemoteMode)
            {
                // 3. Start Hub with backoff (Local Mode Only)
                MonitorProcess(() => StartPythonProcess("dashboard.server", "", "hub.log"), "Hub");

                // 4. Open Browser
                try {
                    Process.Start(new ProcessStartInfo(hubUrl) { UseShellExecute = true });
                } catch (Exception ex) {
                    File.AppendAllText(Path.Combine(logDir, "launcher.log"), "Could not open browser: " + ex.Message + "\n");
                }

                // Wait for controller. Controller crash will restart the whole suite since we exit.
                int initialControllerBackoff = 2000;
                int controllerBackoff = initialControllerBackoff;
                TimeSpan healthyControllerUptimeThreshold = TimeSpan.FromMinutes(2);
                DateTime controllerStartTime = DateTime.UtcNow;

                while (true)
                {
                    if (controllerProc != null)
                    {
                        controllerProc.WaitForExit();
                        
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
                        controllerProc = StartPythonProcess("server.app", "", "controller.log");
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
    }
}


