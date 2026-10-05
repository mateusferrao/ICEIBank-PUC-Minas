# Funcoes de apoio do demo-sprint2.ps1 para organizar as janelas e capturar prints.
# Nao precisa rodar este arquivo diretamente: o demo-sprint2.ps1 carrega ele.
#
# - Fechar-Janela: fecha a janela de terminal que sobrou depois de derrubar uma agencia.
# - Capturar-Print: organiza as janelas (demo + agencias) e salva um PNG so da area
#   delas (nunca a tela inteira, para nao pegar outros programas abertos).

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public struct RECT { public int Left, Top, Right, Bottom; }

public static class Janelas {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool repaint);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h, int attr, out RECT r, int size);

    public static void DpiAware() { SetProcessDPIAware(); }

    public static IntPtr Achar(string titulo) {
        IntPtr achada = IntPtr.Zero;
        EnumWindows((h, l) => {
            if (!IsWindowVisible(h)) return true;
            var sb = new StringBuilder(256);
            GetWindowText(h, sb, 256);
            if (sb.ToString() == titulo) { achada = h; return false; }
            return true;
        }, IntPtr.Zero);
        return achada;
    }

    public static bool Fechar(string titulo) {
        IntPtr h = Achar(titulo);
        if (h == IntPtr.Zero) return false;
        PostMessage(h, 0x0010, IntPtr.Zero, IntPtr.Zero); // WM_CLOSE
        return true;
    }

    // Posiciona a area VISIVEL da janela em (x, y, w, h), descontando a borda invisivel
    // que o Windows 10/11 desenha em volta, e traz a janela para a frente.
    public static void Posicionar(IntPtr h, int x, int y, int w, int hh) {
        ShowWindow(h, 9); // SW_RESTORE
        MoveWindow(h, x, y, w, hh, true);
        RECT outer, vis;
        GetWindowRect(h, out outer);
        DwmGetWindowAttribute(h, 9, out vis, Marshal.SizeOf(typeof(RECT))); // EXTENDED_FRAME_BOUNDS
        int l = vis.Left - outer.Left, t = vis.Top - outer.Top;
        int r = outer.Right - vis.Right, b = outer.Bottom - vis.Bottom;
        MoveWindow(h, x - l, y - t, w + l + r, hh + t + b, true);
        // HWND_TOPMOST, SWP_NOMOVE|SWP_NOSIZE|SWP_SHOWWINDOW
        SetWindowPos(h, new IntPtr(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040);
        SetForegroundWindow(h);
    }

    public static void NaoMaisNoTopo(IntPtr h) {
        SetWindowPos(h, new IntPtr(-2), 0, 0, 0, 0, 0x0001 | 0x0002); // HWND_NOTOPMOST
    }
}
'@

[Janelas]::DpiAware()

function Fechar-Janela($titulo) {
  [void][Janelas]::Fechar($titulo)
}

# modo "lado-a-lado": demo a esquerda, as 3 agencias empilhadas a direita.
# modo "tela-cheia": so a janela do demo, ocupando toda a area de trabalho.
function Capturar-Print($arquivo, $modo) {
  $area = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
  $demo = [Janelas]::Achar("Demo Sprint 2")
  if ($demo -eq [IntPtr]::Zero) { throw "Janela 'Demo Sprint 2' nao encontrada." }
  $envolvidas = @($demo)

  if ($modo -eq "lado-a-lado") {
    $metade = [int]($area.Width / 2)
    $altura = [int]($area.Height / 3)
    [Janelas]::Posicionar($demo, $area.X, $area.Y, $metade, $area.Height)
    for ($i = 0; $i -lt 3; $i++) {
      $h = [Janelas]::Achar("Agencia $i")
      if ($h -eq [IntPtr]::Zero) { continue }
      [Janelas]::Posicionar($h, $area.X + $metade, $area.Y + $i * $altura, $area.Width - $metade, $altura)
      $envolvidas += $h
    }
  } else {
    [Janelas]::Posicionar($demo, $area.X, $area.Y, $area.Width, $area.Height)
  }

  Start-Sleep -Milliseconds 1500   # deixa o Windows redesenhar as janelas
  $bmp = New-Object System.Drawing.Bitmap $area.Width, $area.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($area.X, $area.Y, 0, 0, $bmp.Size)
  $g.Dispose()
  $pasta = Join-Path $PSScriptRoot "..\evidencias\sprint2"
  New-Item -ItemType Directory -Force -Path $pasta | Out-Null
  $caminho = Join-Path (Resolve-Path $pasta) "$arquivo.png"
  $bmp.Save($caminho, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  foreach ($h in $envolvidas) { [Janelas]::NaoMaisNoTopo($h) }
  Write-Host "[print salvo: $caminho]" -ForegroundColor DarkGray
}
