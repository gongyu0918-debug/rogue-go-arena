; GoAI Installer - Inno Setup Script

#define MyAppName "GoAI"
#define MyAppPublisher "GoAI"
#define MyAppExeName "GoAI.exe"
#ifndef MyAppVersion
  #define MyAppVersion GetDateTimeString('yyyy.mm.dd', '-', ':')
#endif
#ifndef RepoRoot
  #define RepoRoot SourcePath
#endif
#ifndef DistDir
  #define DistDir AddBackslash(RepoRoot) + "dist"
#endif
#ifndef ReleaseDir
  #define ReleaseDir AddBackslash(RepoRoot) + "release"
#endif

[Setup]
AppId={{B8F3A2E1-5C7D-4E9A-B6D0-1F2A3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#ReleaseDir}
OutputBaseFilename=GoAI_Setup_{#MyAppVersion}
SetupIconFile={#RepoRoot}\goai.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "chinesesimplified"; MessagesFile: "{#RepoRoot}\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#DistDir}\GoAI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#DistDir}\GoAI_Server\*"; DestDir: "{app}\GoAI_Server"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\katago\*"; DestDir: "{app}\katago"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\server.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\goai.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\goai.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "{#RepoRoot}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\goai.ico"
Name: "{group}\使用说明"; Filename: "{app}\README.md"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\goai.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\README.md"; Description: "查看使用说明"; Flags: nowait postinstall shellexec skipifsilent unchecked
Filename: "{app}\{#MyAppExeName}"; Description: "启动 GoAI"; Flags: nowait postinstall skipifsilent

[Code]
var
  GpuDetected: Boolean;
  GpuName: String;
  DriverVersion: String;
  DriverVersionRaw: String;

function GetPowerShellPath(): String;
begin
  if IsWin64 then
    Result := ExpandConstant('{sysnative}\WindowsPowerShell\v1.0\powershell.exe')
  else
    Result := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  if not FileExists(Result) then
    Result := 'powershell.exe';
end;

function DigitsOnly(const Value: String): String;
var
  I: Integer;
begin
  Result := '';
  for I := 1 to Length(Value) do
  begin
    if (Value[I] >= '0') and (Value[I] <= '9') then
      Result := Result + Value[I];
  end;
end;

function NormalizeNvidiaDriverVersion(const RawVersion: String): String;
var
  Digits: String;
  Tail: String;
begin
  Result := Trim(RawVersion);
  Digits := DigitsOnly(Result);
  if Length(Digits) >= 5 then
  begin
    Tail := Copy(Digits, Length(Digits) - 4, 5);
    Result := IntToStr(StrToIntDef(Copy(Tail, 1, 3), 0)) + '.' + Copy(Tail, 4, 2);
  end;
end;

function RunPowerShellCapture(const Command: String; const TmpFile: String): Boolean;
var
  ResultCode: Integer;
  ShellCmd: String;
begin
  DeleteFile(TmpFile);
  ShellCmd :=
    '/C ""' + GetPowerShellPath() + '" -NoProfile -ExecutionPolicy Bypass -Command "' +
    Command + '" > "' + TmpFile + '" 2>nul"';
  Result := Exec(ExpandConstant('{cmd}'), ShellCmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
    and (ResultCode = 0)
    and FileExists(TmpFile);
end;

function RunGpuDetectViaPowerShell(): Boolean;
var
  TmpFile: String;
  Lines: TArrayOfString;
  Line: String;
  PipePos: Integer;
begin
  Result := False;
  TmpFile := ExpandConstant('{tmp}\goai_gpu_ps.txt');
  if not RunPowerShellCapture(
    '$gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match ''NVIDIA'' } | ' +
    'Select-Object -First 1 Name,DriverVersion; ' +
    'if ($gpu) { Write-Output ($gpu.Name + ''|'' + $gpu.DriverVersion) }',
    TmpFile
  ) then
    Exit;

  if LoadStringsFromFile(TmpFile, Lines) and (GetArrayLength(Lines) > 0) then
  begin
    Line := Trim(Lines[0]);
    PipePos := Pos('|', Line);
    if PipePos > 0 then
    begin
      GpuName := Trim(Copy(Line, 1, PipePos - 1));
      DriverVersionRaw := Trim(Copy(Line, PipePos + 1, Length(Line)));
      DriverVersion := NormalizeNvidiaDriverVersion(DriverVersionRaw);
      GpuDetected := (GpuName <> '');
      Result := GpuDetected;
    end;
  end;
  DeleteFile(TmpFile);
end;

function RunNvidiaSmi(): Boolean;
var
  ResultCode: Integer;
  TmpFile: String;
  NvSmiPath: String;
  Lines: TArrayOfString;
  Line: String;
  CommaPos: Integer;
begin
  Result := False;
  GpuDetected := False;
  GpuName := '';
  DriverVersion := '';
  DriverVersionRaw := '';
  TmpFile := ExpandConstant('{tmp}\goai_gpu.txt');

  NvSmiPath := ExpandConstant('{commonpf}\NVIDIA Corporation\NVSMI\nvidia-smi.exe');
  if not FileExists(NvSmiPath) then
    NvSmiPath := ExpandConstant('{sysnative}\nvidia-smi.exe');
  if not FileExists(NvSmiPath) then
    NvSmiPath := ExpandConstant('{sys}\nvidia-smi.exe');
  if not FileExists(NvSmiPath) then
    NvSmiPath := 'nvidia-smi';

  if Exec('cmd.exe',
    '/C "' + NvSmiPath + '" --query-gpu=name,driver_version --format=csv,noheader > "' + TmpFile + '" 2>&1',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if (ResultCode = 0) and LoadStringsFromFile(TmpFile, Lines) then
    begin
      if GetArrayLength(Lines) > 0 then
      begin
        Line := Trim(Lines[0]);
        if Length(Line) > 0 then
        begin
          CommaPos := Pos(',', Line);
          if CommaPos > 0 then
          begin
            GpuName := Trim(Copy(Line, 1, CommaPos - 1));
            DriverVersion := Trim(Copy(Line, CommaPos + 1, Length(Line)));
            DriverVersionRaw := DriverVersion;
          end else
            GpuName := Line;
          GpuDetected := True;
          Result := True;
        end;
      end;
    end;
    DeleteFile(TmpFile);
  end;
end;

function GetDriverMajor(): Integer;
var
  DotPos: Integer;
  MajorStr: String;
begin
  Result := 0;
  DotPos := Pos('.', DriverVersion);
  if DotPos > 0 then
    MajorStr := Copy(DriverVersion, 1, DotPos - 1)
  else
    MajorStr := DriverVersion;
  Result := StrToIntDef(MajorStr, 0);
end;

function InitializeSetup(): Boolean;
var
  Msg: String;
  DriverMajor: Integer;
begin
  Result := True;
  if not RunNvidiaSmi() then
    RunGpuDetectViaPowerShell();

  if WizardSilent then
    Exit;

  if not GpuDetected then
  begin
    Msg := '╔══════════════════════════════╗' + #13#10 +
           '║    GoAI 环境检测             ║' + #13#10 +
           '╚══════════════════════════════╝' + #13#10#13#10 +
           '⚠ 未检测到 NVIDIA 显卡' + #13#10#13#10 +
           '不用担心! GoAI 内置了 CPU 引擎:' + #13#10 +
           '  ✓ 级位对弈 (18级~1级) — 流畅' + #13#10 +
           '  ✓ Rogue 模式 — 流畅' + #13#10 +
           '  ✓ 大招模式 — 流畅' + #13#10 +
           '  ⚠ 段位对弈 — 推理较慢' + #13#10#13#10 +
           '如有 NVIDIA 显卡请确认已安装驱动。' + #13#10#13#10 +
           '是否继续安装?';
    Result := (MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES);
  end else
  begin
    DriverMajor := GetDriverMajor();

    if DriverMajor < 520 then
    begin
      Msg := '╔══════════════════════════════╗' + #13#10 +
             '║    GoAI 环境检测             ║' + #13#10 +
             '╚══════════════════════════════╝' + #13#10#13#10 +
             '✓ 显卡: ' + GpuName + #13#10 +
             '✗ 驱动: ' + DriverVersion + '  (版本过旧!)' + #13#10#13#10 +
             'GoAI 的 GPU 加速需要驱动版本 ≥ 527.41' + #13#10 +
             '请前往 https://www.nvidia.com/drivers 更新驱动' + #13#10#13#10 +
             '即使不更新, 仍可使用内置 CPU 引擎对弈。' + #13#10#13#10 +
             '是否继续安装?';
      Result := (MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES);
    end else if DriverMajor < 528 then
    begin
      Msg := '╔══════════════════════════════╗' + #13#10 +
             '║    GoAI 环境检测             ║' + #13#10 +
             '╚══════════════════════════════╝' + #13#10#13#10 +
             '✓ 显卡: ' + GpuName + #13#10 +
             '⚠ 驱动: ' + DriverVersion + '  (建议更新)' + #13#10#13#10 +
             '建议更新至 ≥ 528.00 以获得最佳 CUDA 12 支持' + #13#10#13#10 +
             '是否继续安装?';
      Result := (MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES);
    end else
    begin
      MsgBox('╔══════════════════════════════╗' + #13#10 +
             '║    GoAI 环境检测             ║' + #13#10 +
             '╚══════════════════════════════╝' + #13#10#13#10 +
             '✓ 显卡: ' + GpuName + #13#10 +
             '✓ 驱动: ' + DriverVersion + #13#10 +
             '✓ CUDA 支持: 正常' + #13#10#13#10 +
             '您的系统完全满足运行要求!',
             mbInformation, MB_OK);
    end;
  end;
end;
