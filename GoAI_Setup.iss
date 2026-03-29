; GoAI Installer - Inno Setup Script

#define MyAppName "GoAI"
#define MyAppVersion "1.0"
#define MyAppPublisher "GoAI"
#define MyAppExeName "GoAI.exe"

[Setup]
AppId={{B8F3A2E1-5C7D-4E9A-B6D0-1F2A3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=C:\Users\admin\Desktop
OutputBaseFilename=GoAI_Setup
SetupIconFile=C:\Users\admin\Desktop\GoAI\goai.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "chinesesimplified"; MessagesFile: "C:\Users\admin\GoAI\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "C:\Users\admin\Desktop\GoAI\GoAI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\admin\Desktop\GoAI\GoAI_Server\*"; DestDir: "{app}\GoAI_Server"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "C:\Users\admin\Desktop\GoAI\static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "C:\Users\admin\Desktop\GoAI\katago\*"; DestDir: "{app}\katago"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "C:\Users\admin\Desktop\GoAI\server.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\admin\Desktop\GoAI\goai.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\admin\Desktop\GoAI\goai.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\admin\Desktop\GoAI\README.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\goai.ico"
Name: "{group}\使用说明"; Filename: "{app}\README.txt"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\goai.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\README.txt"; Description: "查看使用说明"; Flags: nowait postinstall shellexec skipifsilent unchecked
Filename: "{app}\{#MyAppExeName}"; Description: "启动 GoAI"; Flags: nowait postinstall skipifsilent

[Code]
var
  GpuDetected: Boolean;
  GpuName: String;
  DriverVersion: String;

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
  TmpFile := ExpandConstant('{tmp}\goai_gpu.txt');

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
  RunNvidiaSmi();

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
