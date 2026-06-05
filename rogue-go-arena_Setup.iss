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
DefaultDirName={localappdata}\Programs\{#MyAppName}
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
Name: "chinesetraditional"; MessagesFile: "{#RepoRoot}\ChineseTraditional.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

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
chinesesimplified.DriverNeed=内置 CUDA 12.8 加速建议驱动版本 ≥ 572.61
english.DriverNeed=Bundled CUDA 12.8 acceleration is recommended with driver 572.61 or newer
japanese.DriverNeed=内蔵 CUDA 12.8 アクセラレーションには 572.61 以上のドライバーを推奨します
korean.DriverNeed=내장 CUDA 12.8 가속에는 드라이버 572.61 이상을 권장합니다
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
chinesesimplified.DriverRecommend=建议更新至 ≥ 572.61，以便稳定使用内置 CUDA 12.8 与 RTX 50 系列
english.DriverRecommend=Driver 572.61 or newer is recommended for bundled CUDA 12.8 and RTX 50 series
japanese.DriverRecommend=内蔵 CUDA 12.8 と RTX 50 シリーズを安定して使うには 572.61 以上を推奨します
korean.DriverRecommend=내장 CUDA 12.8 및 RTX 50 시리즈에는 드라이버 572.61 이상을 권장합니다
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
chinesesimplified.RemoveUserDataPrompt=是否同时删除本机用户数据？%n%n这会移除 WebView/Edge 配置、本地 KataGo 缓存、下载模型、日志和卡牌编辑器配置。%n%n选择“否”将只卸载程序文件并保留用户数据。
english.RemoveUserDataPrompt=Remove local user data too?%n%nThis removes WebView/Edge profiles, local KataGo cache, downloaded models, logs, and card editor settings.%n%nChoose No to uninstall program files only and keep user data.
japanese.RemoveUserDataPrompt=ローカルユーザーデータも削除しますか？%n%nWebView/Edge プロファイル、ローカル KataGo キャッシュ、ダウンロード済みモデル、ログ、カードエディター設定が削除されます。%n%n「いいえ」を選ぶと、プログラムファイルのみを削除してユーザーデータは保持します。
korean.RemoveUserDataPrompt=로컬 사용자 데이터도 삭제할까요?%n%nWebView/Edge 프로필, 로컬 KataGo 캐시, 다운로드한 모델, 로그, 카드 편집기 설정이 삭제됩니다.%n%n아니요를 선택하면 프로그램 파일만 제거하고 사용자 데이터는 보관합니다.
chinesetraditional.ReadmeIcon=使用說明
chinesetraditional.RunReadme=查看使用說明
chinesetraditional.RunApp=啟動 rogue-go-arena
chinesetraditional.GpuHeader=rogue-go-arena 環境檢測
chinesetraditional.GpuMissing=⚠ 未偵測到 NVIDIA 顯示卡
chinesetraditional.CpuFallback=不用擔心，內建 CPU 引擎仍可執行：
chinesetraditional.KyuPlayable=✓ 級位對局 (18級~1級) — 流暢
chinesetraditional.RoguePlayable=✓ Rogue 模式 — 流暢
chinesetraditional.UltimatePlayable=✓ Ultimate 模式 — 流暢
chinesetraditional.DanSlow=⚠ 段位對局 — 分析較慢
chinesetraditional.CheckDriver=如有 NVIDIA 顯示卡，請確認已安裝驅動程式。
chinesetraditional.ContinueInstall=是否繼續安裝？
chinesetraditional.GpuLabel=✓ 顯示卡:
chinesetraditional.DriverOld=✗ 驅動程式:
chinesetraditional.DriverOldNote=  (版本過舊!)
chinesetraditional.DriverNeed=內建 CUDA 12.8 加速建議驅動程式版本 ≥ 572.61
chinesetraditional.DriverUpdate=請前往 https://www.nvidia.com/drivers 更新驅動程式
chinesetraditional.CpuStillWorks=即使不更新，仍可使用內建 CPU 引擎對局。
chinesetraditional.DriverWarn=⚠ 驅動程式:
chinesetraditional.DriverWarnNote=  (建議更新)
chinesetraditional.DriverRecommend=建議更新至 ≥ 572.61，以便穩定使用內建 CUDA 12.8 與 RTX 50 系列
chinesetraditional.DriverOk=✓ 驅動程式:
chinesetraditional.CudaOk=✓ CUDA 支援: 正常
chinesetraditional.SystemReady=您的系統符合執行需求!
chinesetraditional.RemoveUserDataPrompt=是否同時刪除本機使用者資料？%n%n這會移除 WebView/Edge 設定檔、本機 KataGo 快取、已下載模型、日誌和卡牌編輯器設定。%n%n選擇「否」將只解除安裝程式檔案並保留使用者資料。
french.ReadmeIcon=README
french.RunReadme=Voir le README
french.RunApp=Lancer rogue-go-arena
french.GpuHeader=Vérification de l'environnement rogue-go-arena
french.GpuMissing=⚠ Aucun GPU NVIDIA détecté
french.CpuFallback=Le moteur CPU intégré peut quand même fonctionner :
french.KyuPlayable=✓ Parties kyu (18k à 1k) — fluide
french.RoguePlayable=✓ Mode Rogue — fluide
french.UltimatePlayable=✓ Mode Ultimate — fluide
french.DanSlow=⚠ Parties dan — analyse plus lente
french.CheckDriver=Si cette machine possède un GPU NVIDIA, vérifiez que le pilote est installé.
french.ContinueInstall=Continuer l'installation ?
french.GpuLabel=✓ GPU :
french.DriverOld=✗ Pilote :
french.DriverOldNote=  (trop ancien !)
french.DriverNeed=L'accélération CUDA 12.8 intégrée est recommandée avec le pilote 572.61 ou plus récent
french.DriverUpdate=Mettez le pilote à jour sur https://www.nvidia.com/drivers
french.CpuStillWorks=Vous pouvez toujours jouer avec le moteur CPU intégré.
french.DriverWarn=⚠ Pilote :
french.DriverWarnNote=  (mise à jour recommandée)
french.DriverRecommend=Le pilote 572.61 ou plus récent est recommandé pour CUDA 12.8 intégré et les RTX série 50
french.DriverOk=✓ Pilote :
french.CudaOk=✓ CUDA : prêt
french.SystemReady=Votre système répond aux prérequis.
french.RemoveUserDataPrompt=Supprimer aussi les données utilisateur locales ?%n%nCela supprime les profils WebView/Edge, le cache KataGo local, les modèles téléchargés, les journaux et les réglages de l'éditeur de cartes.%n%nChoisissez Non pour ne désinstaller que les fichiers du programme et conserver les données utilisateur.
german.ReadmeIcon=README
german.RunReadme=README anzeigen
german.RunApp=rogue-go-arena starten
german.GpuHeader=rogue-go-arena Umgebungsprüfung
german.GpuMissing=⚠ Kein NVIDIA-GPU erkannt
german.CpuFallback=Die integrierte CPU-Engine kann trotzdem laufen:
german.KyuPlayable=✓ Kyu-Partien (18k bis 1k) — flüssig
german.RoguePlayable=✓ Rogue-Modus — flüssig
german.UltimatePlayable=✓ Ultimate-Modus — flüssig
german.DanSlow=⚠ Dan-Partien — langsamere Analyse
german.CheckDriver=Falls dieser Rechner einen NVIDIA-GPU hat, prüfen Sie bitte den installierten Treiber.
german.ContinueInstall=Installation fortsetzen?
german.GpuLabel=✓ GPU:
german.DriverOld=✗ Treiber:
german.DriverOldNote=  (zu alt!)
german.DriverNeed=Für die integrierte CUDA-12.8-Beschleunigung wird Treiber 572.61 oder neuer empfohlen
german.DriverUpdate=Aktualisieren Sie den Treiber unter https://www.nvidia.com/drivers
german.CpuStillWorks=Sie können weiterhin mit der integrierten CPU-Engine spielen.
german.DriverWarn=⚠ Treiber:
german.DriverWarnNote=  (Update empfohlen)
german.DriverRecommend=Für integriertes CUDA 12.8 und RTX-50-GPUs wird Treiber 572.61 oder neuer empfohlen
german.DriverOk=✓ Treiber:
german.CudaOk=✓ CUDA-Unterstützung: bereit
german.SystemReady=Ihr System erfüllt die Laufzeitanforderungen.
german.RemoveUserDataPrompt=Auch lokale Benutzerdaten löschen?%n%nDies entfernt WebView/Edge-Profile, lokalen KataGo-Cache, heruntergeladene Modelle, Logs und Einstellungen des Karteneditors.%n%nWählen Sie Nein, um nur die Programmdateien zu deinstallieren und Benutzerdaten zu behalten.

[Files]
Source: "{#DistDir}\rogue-go-arena.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#DistDir}\rogue-go-arena-server\*"; DestDir: "{app}\rogue-go-arena-server"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "{#RepoRoot}\static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "assets\icons\cards-tech-featured\*,assets\icons\cards-tech\*-sheet.png,assets\icons\cards-tech\featured-card-sheet-tech-v1.png,assets\icons\toolbar-tech\toolbar-sheet-tech-*.png,assets\textures\board-tech-classic-v1.png,assets\textures\stone-materials-tech-v2.png"
Source: "{#RepoRoot}\katago\*"; DestDir: "{app}\katago"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "katago.exe.new,kata_log.txt"
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

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\katago\is-*.tmp"
Type: files; Name: "{app}\katago\katago.exe.new"

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
  RemoveUserDataOnUninstall: Boolean;

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

function GetDriverVersionCode(): Integer;
var
  DotPos: Integer;
  MajorStr: String;
  MinorStr: String;
begin
  Result := 0;
  DotPos := Pos('.', DriverVersion);
  if DotPos > 0 then
  begin
    MajorStr := Copy(DriverVersion, 1, DotPos - 1);
    MinorStr := Copy(DriverVersion, DotPos + 1, Length(DriverVersion));
  end else
  begin
    MajorStr := DriverVersion;
    MinorStr := '0';
  end;
  Result := (StrToIntDef(MajorStr, 0) * 100) + StrToIntDef(Copy(MinorStr, 1, 2), 0);
end;

function InitializeSetup(): Boolean;
var
  Msg: String;
  DriverCode: Integer;
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
    DriverCode := GetDriverVersionCode();

    if (DriverCode > 0) and (DriverCode < 52833) then
    begin
      Msg := GpuHeaderBox() + #13#10#13#10 +
             T('GpuLabel') + ' ' + GpuName + #13#10 +
             T('DriverOld') + ' ' + DriverVersion + T('DriverOldNote') + #13#10#13#10 +
             T('DriverNeed') + #13#10 +
             T('DriverUpdate') + #13#10#13#10 +
             T('CpuStillWorks') + #13#10#13#10 +
             T('ContinueInstall');
      Result := (MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES);
    end else if (DriverCode = 0) or (DriverCode < 57261) then
    begin
      Msg := GpuHeaderBox() + #13#10#13#10 +
             T('GpuLabel') + ' ' + GpuName + #13#10 +
             T('DriverWarn') + ' ' + DriverVersion + T('DriverWarnNote') + #13#10#13#10 +
             T('DriverRecommend') + #13#10#13#10 +
             T('ContinueInstall');
      Result := (MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES);
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

function InitializeUninstall(): Boolean;
begin
  Result := True;
  RemoveUserDataOnUninstall := False;
  if UninstallSilent then
    Exit;

  RemoveUserDataOnUninstall :=
    MsgBox(T('RemoveUserDataPrompt'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: String;
begin
  if (CurUninstallStep = usPostUninstall) and RemoveUserDataOnUninstall then
  begin
    DelTree(ExpandConstant('{app}\gtp_logs'), True, True, True);
    DelTree(ExpandConstant('{app}\output'), True, True, True);
    DeleteFile(ExpandConstant('{app}\katago\kata_log.txt'));
    DeleteFile(ExpandConstant('{app}\katago\model.bin.gz'));
    UserDataDir := ExpandConstant('{localappdata}\rogue-go-arena');
    if DirExists(UserDataDir) then
      DelTree(UserDataDir, True, True, True);
  end;
end;
