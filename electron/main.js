const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let serverProcess;

function getResourcePath(relativePath) {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, relativePath);
  }
  return path.join(__dirname, '..', relativePath);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    autoHideMenuBar: true
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

function startServer() {
  const isWin = process.platform === 'win32';
  const isMac = process.platform === 'darwin';
  
  const backendPath = getResourcePath('backend');
  const serverScript = path.join(backendPath, 'server.py');
  const ffmpegPath = getResourcePath('ffmpeg');
  
  const pythonCmd = isWin ? 'python' : 'python3';
  
  const env = {
    ...process.env,
    PATH: `${ffmpegPath}${path.delimiter}${process.env.PATH}`,
    PYTHONPATH: backendPath
  };

  console.log('Starting server...');
  console.log('Backend path:', backendPath);
  console.log('FFmpeg path:', ffmpegPath);

  serverProcess = spawn(
    pythonCmd,
    ['-m', 'uvicorn', 'server:app', '--port', '8765', '--host', '127.0.0.1'],
    {
      cwd: backendPath,
      env: env,
      shell: true
    }
  );

  serverProcess.stdout.on('data', (data) => {
    console.log(`[Server] ${data.toString()}`);
  });

  serverProcess.stderr.on('data', (data) => {
    console.error(`[Server Error] ${data.toString()}`);
  });

  serverProcess.on('error', (error) => {
    console.error('[Server] Failed to start:', error);
  });

  serverProcess.on('close', (code) => {
    console.log(`[Server] Process exited with code ${code}`);
  });
}

app.whenReady().then(() => {
  startServer();
  
  setTimeout(() => {
    createWindow();
  }, 2000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (serverProcess) {
    serverProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (serverProcess) {
    serverProcess.kill();
  }
});
