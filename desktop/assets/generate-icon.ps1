Add-Type -AssemblyName System.Drawing

$code = @'
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;

public class IconGenerator {
    private static void RoundedRect(GraphicsPath path, float x, float y, float w, float h, float r) {
        float d = r * 2;
        path.AddArc(x + w - d, y, d, d, 270, 90);
        path.AddArc(x + w - d, y + h - d, d, d, 0, 90);
        path.AddArc(x, y + h - d, d, d, 90, 90);
        path.AddArc(x, y, d, d, 180, 90);
        path.CloseFigure();
    }

    private static void DrawIcon(int size, string outPath) {
        Bitmap bmp = new Bitmap(size, size);
        Graphics g = Graphics.FromImage(bmp);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.PixelOffsetMode = PixelOffsetMode.Half;
        float scale = size / 1024f;

        // Background gradient
        LinearGradientBrush bg = new LinearGradientBrush(
            RectangleF.FromLTRB(0, 0, size, size),
            Color.FromArgb(124, 58, 237),
            Color.FromArgb(79, 70, 229),
            LinearGradientMode.BackwardDiagonal
        );
        ColorBlend mid = new ColorBlend(3);
        mid.Colors = new Color[] {
            Color.FromArgb(124, 58, 237),
            Color.FromArgb(99, 102, 241),
            Color.FromArgb(79, 70, 229)
        };
        mid.Positions = new float[] { 0f, 0.5f, 1f };
        bg.InterpolationColors = mid;

        GraphicsPath path = new GraphicsPath();
        float radius = 224 * scale;
        RoundedRect(path, 0, 0, size, size, radius);
        g.FillPath(bg, path);
        bg.Dispose();

        // Outer glow ring
        Pen glowPen = new Pen(Color.FromArgb(60, 167, 139, 250), 6 * scale);
        g.DrawEllipse(glowPen, size * 0.15f, size * 0.15f, size * 0.7f, size * 0.7f);
        glowPen.Dispose();

        // Star particles
        int[][] dots = new int[][] {
            new int[] {320, 280, 8}, new int[] {720, 240, 6}, new int[] {780, 520, 10},
            new int[] {260, 600, 7}, new int[] {700, 760, 9}, new int[] {340, 780, 5}
        };
        foreach (var d in dots) {
            float x = d[0] * scale;
            float y = d[1] * scale;
            float r = d[2] * scale;
            SolidBrush brush = new SolidBrush(Color.FromArgb(150, 255, 255, 255));
            g.FillEllipse(brush, x - r, y - r, r * 2, r * 2);
            brush.Dispose();
        }

        // Main Y shape
        Pen whitePen = new Pen(Color.White, 56 * scale);
        whitePen.StartCap = LineCap.Round;
        whitePen.EndCap = LineCap.Round;
        g.DrawLine(whitePen, 380 * scale, 320 * scale, 512 * scale, 520 * scale);
        g.DrawLine(whitePen, 512 * scale, 520 * scale, 644 * scale, 320 * scale);
        g.DrawLine(whitePen, 512 * scale, 520 * scale, 512 * scale, 740 * scale);
        whitePen.Dispose();

        // Center dot
        SolidBrush dotBrush = new SolidBrush(Color.White);
        g.FillEllipse(dotBrush, (512 - 42) * scale, (512 - 42) * scale, 84 * scale, 84 * scale);
        dotBrush.Dispose();

        // Orbit arcs
        Pen arcPen1 = new Pen(Color.FromArgb(240, 167, 139, 250), 28 * scale);
        arcPen1.StartCap = LineCap.Round;
        arcPen1.EndCap = LineCap.Round;
        g.DrawArc(arcPen1, 420 * scale, 320 * scale, 400 * scale, 400 * scale, -45, 180);
        arcPen1.Dispose();

        Pen arcPen2 = new Pen(Color.FromArgb(220, 96, 165, 250), 28 * scale);
        arcPen2.StartCap = LineCap.Round;
        arcPen2.EndCap = LineCap.Round;
        g.DrawArc(arcPen2, 204 * scale, 320 * scale, 400 * scale, 400 * scale, 135, 180);
        arcPen2.Dispose();

        g.Dispose();
        bmp.Save(outPath, ImageFormat.Png);
        bmp.Dispose();
    }

    private static void DrawIco(string outPath) {
        int[] sizes = new int[] { 256, 128, 64, 48, 32, 16 };
        using (System.IO.MemoryStream ms = new System.IO.MemoryStream()) {
            // ICO header
            ms.WriteByte(0); ms.WriteByte(0);
            ms.WriteByte(1); ms.WriteByte(0);
            ms.WriteByte((byte)sizes.Length); ms.WriteByte(0);
            // Directory + image data placeholders
            long dirOffset = ms.Position;
            long dataOffset = dirOffset + sizes.Length * 16;
            foreach (int s in sizes) {
                ms.WriteByte((byte)(s == 256 ? 0 : s));
                ms.WriteByte((byte)(s == 256 ? 0 : s));
                ms.WriteByte(0);
                ms.WriteByte(0);
                ms.WriteByte(1); ms.WriteByte(0);
                ms.WriteByte(32); ms.WriteByte(0);
                ms.Write(System.BitConverter.GetBytes(0), 0, 4);
                ms.Write(System.BitConverter.GetBytes(0), 0, 4);
            }
            foreach (int s in sizes) {
                Bitmap bmp = new Bitmap(s, s);
                Graphics g = Graphics.FromImage(bmp);
                g.SmoothingMode = SmoothingMode.AntiAlias;
                float scale = s / 1024f;
                LinearGradientBrush bg = new LinearGradientBrush(
                    RectangleF.FromLTRB(0, 0, s, s),
                    Color.FromArgb(124, 58, 237),
                    Color.FromArgb(79, 70, 229),
                    LinearGradientMode.BackwardDiagonal
                );
                ColorBlend mid = new ColorBlend(3);
                mid.Colors = new Color[] {
                    Color.FromArgb(124, 58, 237),
                    Color.FromArgb(99, 102, 241),
                    Color.FromArgb(79, 70, 229)
                };
                mid.Positions = new float[] { 0f, 0.5f, 1f };
                bg.InterpolationColors = mid;
                GraphicsPath path = new GraphicsPath();
                RoundedRect(path, 0, 0, s, s, 224 * scale);
                g.FillPath(bg, path);
                bg.Dispose();
                Pen whitePen = new Pen(Color.White, 56 * scale);
                whitePen.StartCap = LineCap.Round;
                whitePen.EndCap = LineCap.Round;
                g.DrawLine(whitePen, 380 * scale, 320 * scale, 512 * scale, 520 * scale);
                g.DrawLine(whitePen, 512 * scale, 520 * scale, 644 * scale, 320 * scale);
                g.DrawLine(whitePen, 512 * scale, 520 * scale, 512 * scale, 740 * scale);
                whitePen.Dispose();
                SolidBrush dotBrush = new SolidBrush(Color.White);
                g.FillEllipse(dotBrush, (512 - 42) * scale, (512 - 42) * scale, 84 * scale, 84 * scale);
                dotBrush.Dispose();
                g.Dispose();
                using (System.IO.MemoryStream pngMs = new System.IO.MemoryStream()) {
                    bmp.Save(pngMs, ImageFormat.Png);
                    byte[] pngData = pngMs.ToArray();
                    long imgPos = ms.Position;
                    ms.Write(pngData, 0, pngData.Length);
                    // Update directory entry
                    int idx = System.Array.IndexOf(sizes, s);
                    ms.Seek(dirOffset + idx * 16 + 8, System.IO.SeekOrigin.Begin);
                    ms.Write(System.BitConverter.GetBytes((int)pngData.Length), 0, 4);
                    ms.Write(System.BitConverter.GetBytes((int)imgPos), 0, 4);
                    ms.Seek(imgPos + pngData.Length, System.IO.SeekOrigin.Begin);
                }
                bmp.Dispose();
            }
            System.IO.File.WriteAllBytes(outPath, ms.ToArray());
        }
    }

    public static void Main(string[] args) {
        string dir = args.Length > 0 ? args[0] : System.IO.Directory.GetCurrentDirectory();
        DrawIcon(512, System.IO.Path.Combine(dir, "icon.png"));
        DrawIcon(64, System.IO.Path.Combine(dir, "tray-icon.png"));
        DrawIco(System.IO.Path.Combine(dir, "icon.ico"));
    }
}
'@

Add-Type -TypeDefinition $code -ReferencedAssemblies System.Drawing
[IconGenerator]::Main(@($PSScriptRoot))
Write-Host "Icon generation complete"
