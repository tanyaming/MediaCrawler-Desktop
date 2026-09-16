; ============================================================
;  MediaCrawler 桌面版 —— Inno Setup 安装脚本
;  用法:  iscc desktop\installer.iss
;  产物:  dist\MediaCrawler-Setup-<version>.exe
;  依赖:  需先用 PyInstaller 打包出 dist\MediaCrawler\
; ============================================================

#define MyAppName "MediaCrawler"
#define MyAppDisplayName "舆情采集器"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "舆情采集器"
#define MyAppExeName "MediaCrawler.exe"

[Setup]
AppId={{8F3A2C91-4B7D-4E56-9A1C-MEDIACRAWLER01}
AppName={#MyAppDisplayName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppDisplayName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=舆情采集器-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableDirPage=no
AllowNoIcons=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: checkedonce

[Files]
Source: "..\dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppDisplayName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppDisplayName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WizardSilent) then
  begin
    MsgBox('感谢安装舆情采集器！使用前请确保本机已安装 Chrome 或 Edge 浏览器（用于扫码登录）。数据默认保存于 %APPDATA% 下的 MediaCrawler 目录。', mbInformation, MB_OK);
  end;
end;
