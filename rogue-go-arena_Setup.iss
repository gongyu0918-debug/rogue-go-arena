; rogue-go-arena Installer - Inno Setup Script

#define MyAppName "rogue-go-arena"
#define MyAppPublisher "rogue-go-arena"
#define MyAppExeName "rogue-go-arena.exe"
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
DefaultDirName=F:\{#MyAppName}
UsePreviousAppDir=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#ReleaseDir}
OutputBaseFilename=rogue-go-arena_Setup_{#MyAppVersion}
SetupIconFile={#RepoRoot}\rogue-go-arena.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "chinesesimplified"; MessagesFile: "{#RepoRoot}\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[CustomMessages]
chinesesimplified.ReadmeIcon=使用说明
english.ReadmeIcon=README
japanese.ReadmeIcon=README
korean.ReadmeIcon=README
chinesesimplified.RunReadme=查看使用说明
english.RunReadme=View README
japanese.RunReadme=README を表示
korean.RunReadme=README 보기
chinesesimplified.RunApp=启动 rogue-go-arena
english.RunApp=Launch rogue-go-arena
japanese.RunApp=rogue-go-arena を起動
korean.RunApp=rogue-go-arena 실행
chinesesimplified.GpuHeader=rogue-go-arena 环境检测
english.GpuHeader=rogue-go-arena environment check
japanese.GpuHeader=rogue-go-arena 環境チェック
korean.GpuHeader=rogue-go-arena 환경 검사
chinesesimplified.GpuMissing=⚠ 未检测到 NVIDIA 显卡
english.GpuMissing=⚠ NVIDIA GPU was not detected
japanese.GpuMissing=⚠ NVIDIA GPU が検出されませんでした
korean.GpuMissing=⚠ NVIDIA GPU를 감지하지 못했습니다
chinesesimplified.CpuFallback=不用担心，内置 CPU 引擎仍可运行：
english.CpuFallback=The built-in CPU engine can still run:
japanese.CpuFallback=内蔵 CPU エンジンでも実行できます:
korean.CpuFallback=내장 CPU 엔진으로도 실행할 수 있습니다:
chinesesimplified.KyuPlayable=✓ 级位对弈 (18级~1级) — 流畅
english.KyuPlayable=✓ Kyu games (18k to 1k) — smooth
japanese.KyuPlayable=✓ 級位対局 (18級〜1級) — 快適
korean.KyuPlayable=✓ 급수 대국 (18급~1급) — 원활
chinesesimplified.RoguePlayable=✓ Rogue 模式 — 流畅
english.RoguePlayable=✓ Rogue mode — smooth
japanese.RoguePlayable=✓ Rogue モード — 快適
korean.RoguePlayable=✓ Rogue 모드 — 원활
chinesesimplified.UltimatePlayable=✓ Ultimate 模式 — 流畅
english.UltimatePlayable=✓ Ultimate mode — smooth
japanese.UltimatePlayable=✓ Ultimate モード — 快適
korean.UltimatePlayable=✓ Ultimate 모드 — 원활
chinesesimplified.DanSlow=⚠ 段位对弈 — 推理较慢
english.DanSlow=⚠ Dan games — slower analysis
japanese.DanSlow=⚠ 段位対局 — 解析は遅め
korean.DanSlow=⚠ 단위 대국 — 분석이 느릴 수 있음
chinesesimplified.CheckDriver=如有 NVIDIA 显卡请确认已安装驱动。
english.CheckDriver=If this machine has an NVIDIA GPU, check that the driver is installed.
japanese.CheckDriver=NVIDIA GPU がある場合は、ドライバーのインストールを確認してください。
korean.CheckDriver=NVIDIA GPU가 있다면 드라이버 설치 상태를 확인하세요.
chinesesimplified.ContinueInstall=是否继续安装？
english.ContinueInstall=Continue installation?
japanese.ContinueInstall=インストールを続行しますか？
korean.ContinueInstall=설치를 계속할까요?
chinesesimplified.GpuLabel=✓ 显卡: 
english.GpuLabel=✓ GPU: 
japanese.GpuLabel=✓ GPU: 
korean.GpuLabel=✓ GPU: 
chinesesimplified.DriverOld=✗ 驱动: 
english.DriverOld=✗ Driver: 
japanese.DriverOld=✗ ドライバー: 
korean.DriverOld=✗ 드라이버: 
chinesesimplified.DriverOldNote=  (版本过旧!)
english.DriverOldNote=  (too old!)
japanese.DriverOldNote=  (古すぎます)
korean.DriverOldNote=  (너무 오래됨)
chinesesimplified.DriverNeed=GPU 加速需要驱动版本 ≥ 527.41
english.DriverNeed=GPU acceleration requires driver version 527.41 or newer
japanese.DriverNeed=GPU アクセラレーションには 527.41 以上のドライバーが必要です
korean.DriverNeed=GPU 가속에는 527.41 이상의 드라이버가 필요합니다
chinesesimplified.DriverUpdate=请前往 https://www.nvidia.com/drivers 更新驱动
english.DriverUpdate=Update the driver at https://www.nvidia.com/drivers
japanese.DriverUpdate=https://www.nvidia.com/drivers からドライバーを更新してください
korean.DriverUpdate=https://www.nvidia.com/drivers 에서 드라이버를 업데이트하세요
chinesesimplified.CpuStillWorks=即使不更新，仍可使用内置 CPU 引擎对弈。
english.CpuStillWorks=You can still play with the built-in CPU engine.
japanese.CpuStillWorks=更新しなくても内蔵 CPU エンジンで対局できます。
korean.CpuStillWorks=업데이트하지 않아도 내장 CPU 엔진으로 대국할 수 있습니다.
chinesesimplified.DriverWarn=⚠ 驱动: 
english.DriverWarn=⚠ Driver: 
japanese.DriverWarn=⚠ ドライバー: 
korean.DriverWarn=⚠ 드라이버: 
chinesesimplified.DriverWarnNote=  (建议更新)
english.DriverWarnNote=  (update recommended)
japanese.DriverWarnNote=  (更新推奨)
korean.DriverWarnNote=  (업데이트 권장)
chinesesimplified.DriverRecommend=建议更新至 ≥ 528.00 以获得最佳 CUDA 12 支持
english.DriverRecommend=Driver 528.00 or newer is recommended for best CUDA 12 support
japanese.DriverRecommend=CUDA 12 を安定して使うには 528.00 以上を推奨します
korean.DriverRecommend=CUDA 12 지원을 위해 528.00 이상을 권장합니다
chinesesimplified.DriverOk=✓ 驱动: 
english.DriverOk=✓ Driver: 
japanese.DriverOk=✓ ドライバー: 
korean.DriverOk=✓ 드라이버: 
chinesesimplified.CudaOk=✓ CUDA 支持: 正常
english.CudaOk=✓ CUDA support: ready
japanese.CudaOk=✓ CUDA サポート: 正常
korean.CudaOk=✓ CUDA 지원: 정상
chinesesimplified.SystemReady=您的系统满足运行要求!
english.SystemReady=Your system meets the runtime requirements.
japanese.SystemReady=このシステムは実行要件を満たしています。
korean.SystemReady=시스템이 실행 요구 사항을 충족합니다.

[Files]
Source: "{#DistDir}\rogue-go-arena.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#DistDir}\rogue-go-arena-server\*"; DestDir: "{app}\rogue-go-arena-server"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "{#RepoRoot}\static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "assets\icons\cards-tech-featured\*,assets\icons\cards-tech\*-sheet.png,assets\icons\cards-tech\featured-card-sheet-tech-v1.png,assets\icons\toolbar-tech\toolbar-sheet-tech-*.png,assets\textures\board-tech-classic-v1.png,assets\textures\stone-materials-tech-v2.png"
Source: "{#RepoRoot}\katago\*"; DestDir: "{app}\katago"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "katago.exe.new,model.bin.gz,kata_log.txt"
Source: "{#RepoRoot}\server.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\rogue-go-arena.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\rogue-go-arena.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\launcher_bg_app.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "{#RepoRoot}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{app}\katago\katago.exe.new"
Type: files; Name: "{app}\katago\is-*.tmp"
Type: files; Name: "{app}\katago\model.bin.gz"
Type: files; Name: "{app}\katago\kata_log.txt"
Type: filesandordirs; Name: "{app}\static\assets\icons\cards-tech-featured"
Type: files; Name: "{app}\static\assets\icons\cards-tech\featured-card-sheet-tech-v1.png"
Type: files; Name: "{app}\static\assets\icons\cards-tech\ig_06e57272b1184deb0169e8dcf2f0f8819885f9a1cae557b618-sheet.png"
Type: files; Name: "{app}\static\assets\icons\cards-tech\ig_06e57272b1184deb0169e8dd3fcf1481988abcbebf8b621e56-sheet.png"
Type: files; Name: "{app}\static\assets\icons\cards-tech\ig_06e57272b1184deb0169e8dd99fc008198b9536bed2eaddc83-sheet.png"
Type: files; Name: "{app}\static\assets\icons\cards-tech\ig_06e57272b1184deb0169e8dded4f448198988ee3c4d926203b-sheet.png"
Type: files; Name: "{app}\static\assets\icons\toolbar-tech\toolbar-sheet-tech-v1.png"
Type: files; Name: "{app}\static\assets\icons\toolbar-tech\toolbar-sheet-tech-v2.png"
Type: files; Name: "{app}\static\assets\textures\board-tech-classic-v1.png"
Type: files; Name: "{app}\static\assets\textures\stone-materials-tech-v2.png"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\rogue-go-arena.ico"
Name: "{group}\{cm:ReadmeIcon}"; Filename: "{app}\README.md"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\rogue-go-arena.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\README.md"; Description: "{cm:RunReadme}"; Flags: nowait postinstall shellexec skipifsilent unchecked
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:RunApp}"; Flags: nowait postinstall skipifsilent

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

function T(const Key: String): String;
begin
  Result := ExpandConstant('{cm:' + Key + '}');
end;

function GpuHeaderBox(): String;
begin
  Result := '╔══════════════════════════════╗' + #13#10 +
            '║    ' + T('GpuHeader') + #13#10 +
            '╚══════════════════════════════╝';
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
  TmpFile := ExpandConstant('{tmp}\rogue_go_arena_gpu_ps.txt');
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
  TmpFile := ExpandConstant('{tmp}\rogue_go_arena_gpu.txt');

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
    Msg := GpuHeaderBox() + #13#10#13#10 +
           T('GpuMissing') + #13#10#13#10 +
           T('CpuFallback') + #13#10 +
           '  ' + T('KyuPlayable') + #13#10 +
           '  ' + T('RoguePlayable') + #13#10 +
           '  ' + T('UltimatePlayable') + #13#10 +
           '  ' + T('DanSlow') + #13#10#13#10 +
           T('CheckDriver') + #13#10#13#10 +
           T('ContinueInstall');
    Result := (MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES);
  end else
  begin
    DriverMajor := GetDriverMajor();

    if DriverMajor < 520 then
    begin
      Msg := GpuHeaderBox() + #13#10#13#10 +
             T('GpuLabel') + GpuName + #13#10 +
             T('DriverOld') + DriverVersion + T('DriverOldNote') + #13#10#13#10 +
             T('DriverNeed') + #13#10 +
             T('DriverUpdate') + #13#10#13#10 +
             T('CpuStillWorks') + #13#10#13#10 +
             T('ContinueInstall');
      Result := (MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES);
    end else if DriverMajor < 528 then
    begin
      Msg := GpuHeaderBox() + #13#10#13#10 +
             T('GpuLabel') + GpuName + #13#10 +
             T('DriverWarn') + DriverVersion + T('DriverWarnNote') + #13#10#13#10 +
             T('DriverRecommend') + #13#10#13#10 +
             T('ContinueInstall');
      Result := (MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES);
    end else
    begin
      MsgBox(GpuHeaderBox() + #13#10#13#10 +
             T('GpuLabel') + GpuName + #13#10 +
             T('DriverOk') + DriverVersion + #13#10 +
             T('CudaOk') + #13#10#13#10 +
             T('SystemReady'),
             mbInformation, MB_OK);
    end;
  end;
end;

procedure DeleteKatagoInstallTemps();
var
  FindRec: TFindRec;
  KatagoDir: String;
begin
  KatagoDir := ExpandConstant('{app}\katago');
  if FindFirst(KatagoDir + '\is-*.tmp', FindRec) then
  begin
    try
      repeat
        DeleteFile(KatagoDir + '\' + FindRec.Name);
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) or (CurStep = ssDone) then
    DeleteKatagoInstallTemps();
end;

procedure DeinitializeSetup();
begin
  DeleteKatagoInstallTemps();
end;
