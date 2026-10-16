using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.IO;
using System.Windows.Forms;
using System.Security.Principal;
using System.Net;
using System.Threading;
using System.Text.RegularExpressions;

namespace CourierLauncher
{
    static class Program
    {
        // P/Invoke for Job Objects
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        static extern IntPtr CreateJobObject(IntPtr a, string lpName);

        [DllImport("kernel32.dll")]
        static extern bool SetInformationJobObject(IntPtr hJob, int infoClass, ref JOBOBJECT_EXTENDED_LIMIT_INFORMATION lpJobObjectInfo, int cbJobObjectInfoLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

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

        static bool IsAdministrator()
        {
            WindowsIdentity identity = WindowsIdentity.GetCurrent();
            WindowsPrincipal principal = new WindowsPrincipal(identity);
            return principal.IsInRole(WindowsBuiltInRole.Administrator);
        }

        static void Elevate()
        {
            ProcessStartInfo processInfo = new ProcessStartInfo(Application.ExecutablePath);
            processInfo.UseShellExecute = true;
            processInfo.Verb = "runas";
            try
            {
                Process.Start(processInfo);
            }
            catch { }
            Environment.Exit(0);
        }

        static string dataDir;
        static string configPath;
        static string logDir;
        static string logPath;
        static string pidPath;
        static string serverUrl = "";
        static string workerId = "";
        static string apiKey = "";

        static NotifyIcon trayIcon;
        static Thread workerThread;
        static bool isStopping = false;
        static Process currentProcess = null;
        static IntPtr hJob;

        [STAThread]
        static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            if (!IsAdministrator() && Environment.GetEnvironmentVariable("COURIER_TEST_NO_JOB") != "1")
            {
                Elevate();
                return;
            }

            dataDir = Environment.ExpandEnvironmentVariables(@"%LOCALAPPDATA%\Courier");
            configPath = Path.Combine(dataDir, "config.json");
            logDir = Path.Combine(dataDir, "logs");
            logPath = Path.Combine(logDir, "worker.log");
            pidPath = Path.Combine(dataDir, "worker.pid");

            if (!Directory.Exists(logDir)) Directory.CreateDirectory(logDir);

            // Zombie prevention
            if (File.Exists(pidPath))
            {
                try
                {
                    int oldPid = int.Parse(File.ReadAllText(pidPath));
                    Process oldProc = Process.GetProcessById(oldPid);
                    if (oldProc.ProcessName.IndexOf("Courier", StringComparison.OrdinalIgnoreCase) >= 0 || oldProc.ProcessName.IndexOf("python", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        if (Environment.GetEnvironmentVariable("COURIER_TEST_NO_JOB") != "1")
                        {
                            MessageBox.Show("Courier Worker is already running.", "Courier");
                        }
                        return;
                    }
                }
                catch { }
            }
            
            File.WriteAllText(pidPath, Process.GetCurrentProcess().Id.ToString());

            // Scheduled Task Register
            if (Environment.GetEnvironmentVariable("COURIER_TEST_NO_JOB") != "1")
            {
                RegisterScheduledTask();
            }

            LoadConfig();

            if (Environment.GetEnvironmentVariable("COURIER_TEST_NO_JOB") == "1")
            {
                serverUrl = "http://127.0.0.1:8800";
                workerId = "test-worker";
                apiKey = "test-key";
            }
            else if (string.IsNullOrEmpty(serverUrl) || string.IsNullOrEmpty(apiKey))
            {
                if (!PromptConfig()) return;
            }

            if (Environment.GetEnvironmentVariable("COURIER_TEST_NO_JOB") != "1")
            {
                if (!PerformHealthCheck())
                {
                    MessageBox.Show("Server unreachable or rejected API key.", "Courier", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }
            }

            SetupTray();

            hJob = CreateJobObject(IntPtr.Zero, null);
            var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            int length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            SetInformationJobObject(hJob, JobObjectExtendedLimitInformation, ref info, length);

            workerThread = new Thread(WorkerLoop);
            workerThread.IsBackground = true;
            workerThread.Start();

            Application.Run();
        }

        static void RegisterScheduledTask()
        {
            string taskName = "CourierWindowsWorker";
            string exePath = Application.ExecutablePath;
            string checkCmd = string.Format("schtasks /query /TN {0}", taskName);
            ProcessStartInfo psiCheck = new ProcessStartInfo("cmd.exe", string.Format("/c {0}", checkCmd)) { CreateNoWindow = true, UseShellExecute = false, RedirectStandardOutput = true };
            using (var p = Process.Start(psiCheck))
            {
                p.WaitForExit();
                if (p.ExitCode != 0)
                {
                    string createCmd = string.Format("schtasks /create /TN {0} /TR \"{1}\" /SC ONLOGON /RL HIGHEST /F", taskName, exePath);
                    ProcessStartInfo psiCreate = new ProcessStartInfo("cmd.exe", string.Format("/c {0}", createCmd)) { CreateNoWindow = true, UseShellExecute = false };
                    Process.Start(psiCreate).WaitForExit();
                }
            }
        }

        static void LoadConfig()
        {
            if (File.Exists(configPath))
            {
                string json = File.ReadAllText(configPath);
                Match mServer = Regex.Match(json, "\"COURIER_SERVER\"\\s*:\\s*\"([^\"]+)\"");
                if (mServer.Success) serverUrl = mServer.Groups[1].Value;
                Match mWorker = Regex.Match(json, "\"COURIER_WORKER_ID\"\\s*:\\s*\"([^\"]+)\"");
                if (mWorker.Success) workerId = mWorker.Groups[1].Value;
                Match mApi = Regex.Match(json, "\"COURIER_API_KEY\"\\s*:\\s*\"([^\"]+)\"");
                if (mApi.Success) apiKey = mApi.Groups[1].Value;
            }
        }

        static bool PromptConfig()
        {
            Form form = new Form { Text = "Courier Configuration", Size = new System.Drawing.Size(400, 250), StartPosition = FormStartPosition.CenterScreen, FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false };
            Label lblServer = new Label { Text = "Server URL:", Left = 20, Top = 20, Width = 100 };
            TextBox txtServer = new TextBox { Left = 120, Top = 20, Width = 200, Text = serverUrl == "" ? "http://127.0.0.1:8080" : serverUrl };
            Label lblWorker = new Label { Text = "Worker ID:", Left = 20, Top = 60, Width = 100 };
            TextBox txtWorker = new TextBox { Left = 120, Top = 60, Width = 200, Text = workerId == "" ? Environment.MachineName : workerId };
            Label lblApi = new Label { Text = "API Key:", Left = 20, Top = 100, Width = 100 };
            TextBox txtApi = new TextBox { Left = 120, Top = 100, Width = 200, Text = apiKey };

            Button btnSave = new Button { Text = "Save", Left = 120, Top = 140, Width = 100 };
            btnSave.Click += delegate {
                serverUrl = txtServer.Text;
                workerId = txtWorker.Text;
                apiKey = txtApi.Text;
                if (!Directory.Exists(dataDir)) Directory.CreateDirectory(dataDir);
                string j = string.Format("{{\n  \"COURIER_SERVER\": \"{0}\",\n  \"COURIER_WORKER_ID\": \"{1}\",\n  \"COURIER_API_KEY\": \"{2}\"\n}}", serverUrl, workerId, apiKey);
                File.WriteAllText(configPath, j);
                form.DialogResult = DialogResult.OK;
                form.Close();
            };

            form.Controls.Add(lblServer); form.Controls.Add(txtServer);
            form.Controls.Add(lblWorker); form.Controls.Add(txtWorker);
            form.Controls.Add(lblApi); form.Controls.Add(txtApi);
            form.Controls.Add(btnSave);
            form.AcceptButton = btnSave;
            return form.ShowDialog() == DialogResult.OK;
        }

        static bool PerformHealthCheck()
        {
            try
            {
                string u = serverUrl.TrimEnd('/') + "/api/status";
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create(u);
                req.Timeout = 5000;
                if (!string.IsNullOrEmpty(apiKey)) {
                    req.Headers.Add("Authorization", "Bearer " + apiKey);
                }
                using (HttpWebResponse res = (HttpWebResponse)req.GetResponse())
                {
                    return res.StatusCode == HttpStatusCode.OK;
                }
            }
            catch { return false; }
        }

        static void SetupTray()
        {
            trayIcon = new NotifyIcon();
            trayIcon.Text = string.Format("Courier Worker ({0}) - Online", workerId);
            // Create a simple icon
            System.Drawing.Bitmap bmp = new System.Drawing.Bitmap(16, 16);
            using (System.Drawing.Graphics g = System.Drawing.Graphics.FromImage(bmp)) { g.Clear(System.Drawing.Color.Green); }
            trayIcon.Icon = System.Drawing.Icon.FromHandle(bmp.GetHicon());
            trayIcon.Visible = true;

            ContextMenu menu = new ContextMenu();
            menu.MenuItems.Add("Change Server/Key", delegate {
                if (PromptConfig())
                {
                    StopWorker();
                    workerThread = new Thread(WorkerLoop);
                    workerThread.IsBackground = true;
                    isStopping = false;
                    workerThread.Start();
                }
            });
            menu.MenuItems.Add("Stop Worker", delegate {
                StopWorker();
            });
            menu.MenuItems.Add("Exit", delegate {
                isStopping = true;
                StopWorker();
                trayIcon.Visible = false;
                Application.Exit();
            });
            trayIcon.ContextMenu = menu;
        }

        static void StopWorker()
        {
            isStopping = true;
            try
            {
                if (currentProcess != null && !currentProcess.HasExited)
                {
                    currentProcess.Kill();
                }
            }
            catch { }
        }

        static void WorkerLoop()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string workerModule = "courier_worker.host";
            string pythonExe = "uv";
            string arguments = string.Format("run python -m {0} --home \"{1}\" --controller \"{2}\" --worker-id \"{3}\"", workerModule, dataDir, serverUrl, workerId);

            if (File.Exists(Path.Combine(baseDir, "python", "python.exe")))
            {
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

            object logLock = new object();
            DataReceivedEventHandler logHandler = (sender, e) => {
                if (e.Data != null) {
                    lock (logLock) {
                        try
                        {
                            if (File.Exists(logPath))
                            {
                                FileInfo fi = new FileInfo(logPath);
                                if (fi.Length > 5 * 1024 * 1024)
                                {
                                    string backupPath = logPath + ".1";
                                    if (File.Exists(backupPath)) File.Delete(backupPath);
                                    File.Move(logPath, backupPath);
                                }
                            }
                        }
                        catch { }
                        File.AppendAllText(logPath, string.Format("[{0:O}] {1}{2}", DateTime.UtcNow, e.Data, Environment.NewLine));
                    }
                }
            };

            while (!isStopping)
            {
                try
                {
                    currentProcess = new Process();
                    currentProcess.StartInfo = psi;
                    currentProcess.OutputDataReceived += logHandler;
                    currentProcess.ErrorDataReceived += logHandler;

                    currentProcess.Start();
                    currentProcess.BeginOutputReadLine();
                    currentProcess.BeginErrorReadLine();

                    AssignProcessToJobObject(hJob, currentProcess.Handle);

                    currentProcess.WaitForExit();
                    lock (logLock) {
                        File.AppendAllText(logPath, string.Format("[{0:O}] Worker exited. Restarting in 5s...{1}", DateTime.UtcNow, Environment.NewLine));
                    }
                    if (isStopping) break;
                    Thread.Sleep(5000);
                }
                catch (Exception ex)
                {
                    lock (logLock) {
                        File.AppendAllText(logPath, string.Format("[{0:O}] Error: {1}{2}", DateTime.UtcNow, ex.ToString(), Environment.NewLine));
                    }
                    Thread.Sleep(5000);
                }
            }
        }
    }
}
