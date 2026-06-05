using Godot;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;

public partial class RuntimeWorker : Node
{
    [Export]
    public bool NoKataGoInEditor { get; set; } = true;

    private Process? _process;
    private int _nextRequestId = 1;

    public bool IsRunning => _process is { HasExited: false };

    public override void _ExitTree()
    {
        Shutdown();
    }

    public string Request(string command, Dictionary<string, object?> payload)
    {
        payload["id"] = NextId();
        payload["command"] = command;
        return SendPayload(payload);
    }

    public string SendAction(Dictionary<string, object?> payload)
    {
        payload["id"] = NextId();
        return SendPayload(payload);
    }

    public void Shutdown()
    {
        if (!IsRunning || _process == null)
        {
            return;
        }
        try
        {
            Request("shutdown", new Dictionary<string, object?>());
            if (!_process.WaitForExit(2500))
            {
                _process.Kill(entireProcessTree: true);
            }
        }
        catch
        {
            try
            {
                if (!_process.HasExited)
                {
                    _process.Kill(entireProcessTree: true);
                }
            }
            catch
            {
                // Best-effort cleanup during game shutdown.
            }
        }
        finally
        {
            _process.Dispose();
            _process = null;
        }
    }

    private string SendPayload(Dictionary<string, object?> payload)
    {
        EnsureStarted();
        if (_process?.StandardInput == null || _process.StandardOutput == null)
        {
            throw new InvalidOperationException("runtime worker is not connected");
        }

        var json = JsonSerializer.Serialize(payload);
        _process.StandardInput.WriteLine(json);
        _process.StandardInput.Flush();
        return _process.StandardOutput.ReadLine() ?? "{\"ok\":false,\"error\":\"worker closed stdout\"}";
    }

    private void EnsureStarted()
    {
        if (IsRunning)
        {
            return;
        }

        var repoRoot = ResolveRepoRoot();
        var workerPath = Path.Combine(repoRoot, "go_runtime_worker.py");
        if (!File.Exists(workerPath))
        {
            throw new FileNotFoundException("go_runtime_worker.py not found", workerPath);
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = ResolvePython(repoRoot),
            WorkingDirectory = repoRoot,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        startInfo.ArgumentList.Add(workerPath);
        if (NoKataGoInEditor && OS.IsDebugBuild())
        {
            startInfo.ArgumentList.Add("--no-katago");
        }

        _process = Process.Start(startInfo) ?? throw new InvalidOperationException("failed to start runtime worker");
        _process.ErrorDataReceived += (_, args) =>
        {
            if (!string.IsNullOrWhiteSpace(args.Data))
            {
                GD.PrintErr(args.Data);
            }
        };
        _process.BeginErrorReadLine();
    }

    private static string ResolveRepoRoot()
    {
        var projectDir = ProjectSettings.GlobalizePath("res://");
        return Path.GetFullPath(Path.Combine(projectDir, ".."));
    }

    private static string ResolvePython(string repoRoot)
    {
        var venvPython = Path.Combine(repoRoot, ".venv", "Scripts", "python.exe");
        return File.Exists(venvPython) ? venvPython : "python";
    }

    private string NextId()
    {
        return $"godot-{_nextRequestId++}";
    }
}
