// Meu Dinheiro para Windows: abre o app web numa janela própria.
// O app é sempre a versão mais nova publicada; login e dados ficam no Supabase.
const { app, BrowserWindow, shell, Menu } = require('electron');
const path = require('path');

const URL_APP = 'https://mtsantos4.github.io/meu-dinheiro/';
let win;

if (!app.requestSingleInstanceLock()) { app.quit(); }
app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });

function criarJanela() {
  win = new BrowserWindow({
    width: 1320, height: 860, minWidth: 380, minHeight: 600,
    title: 'Meu Dinheiro', backgroundColor: '#f4f6f5', show: false,
    icon: path.join(__dirname, 'build', 'icon.png'),
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, sandbox: true }
  });
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Exibir', submenu: [
      { label: 'Recarregar', accelerator: 'F5', click: () => win.webContents.reloadIgnoringCache() },
      { role: 'resetZoom', label: 'Tamanho normal' }, { role: 'zoomIn', label: 'Aumentar' }, { role: 'zoomOut', label: 'Diminuir' },
      { type: 'separator' }, { role: 'togglefullscreen', label: 'Tela cheia' }
    ]}
  ]));
  win.once('ready-to-show', () => win.show());
  win.loadURL(URL_APP);

  // Sem internet: mostra aviso e tenta de novo
  win.webContents.on('did-fail-load', (_e, code, _desc, url, isMain) => {
    if (isMain && code !== -3) win.loadFile(path.join(__dirname, 'offline.html'));
  });

  // Links de outros sites abrem no navegador padrão
  const ehDoApp = u => u.startsWith(URL_APP) || u.startsWith('file:');
  win.webContents.setWindowOpenHandler(({ url }) => { if (!ehDoApp(url)) shell.openExternal(url); return { action: 'deny' }; });
  win.webContents.on('will-navigate', (e, url) => { if (!ehDoApp(url)) { e.preventDefault(); shell.openExternal(url); } });
}

app.whenReady().then(criarJanela);
app.on('window-all-closed', () => app.quit());
