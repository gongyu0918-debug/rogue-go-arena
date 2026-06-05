using Godot;
using System;
using System.IO;

public partial class BoardView : Control
{
    [Signal]
    public delegate void PointSelectedEventHandler(int x, int y);

    [Export]
    public int BoardSize { get; set; } = 9;

    private int[,] _board = new int[9, 9];
    private Vector2I? _hoverPoint;
    private Texture2D? _boardTexture;
    private Texture2D? _blackStoneTexture;
    private Texture2D? _whiteStoneTexture;

    public override void _Ready()
    {
        MouseFilter = MouseFilterEnum.Stop;
        LoadStaticAssets();
    }

    public void SetBoard(int[][] board)
    {
        if (board.Length == 0)
        {
            return;
        }
        BoardSize = board.Length;
        _board = new int[BoardSize, BoardSize];
        for (var y = 0; y < BoardSize; y++)
        {
            for (var x = 0; x < BoardSize && x < board[y].Length; x++)
            {
                _board[x, y] = board[y][x];
            }
        }
        QueueRedraw();
    }

    public override void _Draw()
    {
        var rect = GetRect();
        var side = MathF.Min(rect.Size.X, rect.Size.Y);
        var boardRect = new Rect2(
            new Vector2((rect.Size.X - side) * 0.5f, (rect.Size.Y - side) * 0.5f),
            new Vector2(side, side)
        );
        if (_boardTexture != null)
        {
            DrawTextureRect(_boardTexture, boardRect, false);
        }
        else
        {
            DrawRect(boardRect, new Color(0.66f, 0.43f, 0.21f), true);
        }
        DrawRect(boardRect, new Color(0.22f, 0.12f, 0.05f), false, 4f);

        var padding = side * 0.075f;
        var gridSide = side - padding * 2f;
        var step = BoardSize > 1 ? gridSide / (BoardSize - 1) : gridSide;
        var origin = boardRect.Position + new Vector2(padding, padding);
        var lineColor = new Color(0.16f, 0.09f, 0.035f, 0.86f);

        for (var i = 0; i < BoardSize; i++)
        {
            var offset = i * step;
            DrawLine(origin + new Vector2(offset, 0), origin + new Vector2(offset, gridSide), lineColor, 1.4f);
            DrawLine(origin + new Vector2(0, offset), origin + new Vector2(gridSide, offset), lineColor, 1.4f);
        }

        foreach (var star in StarPoints(BoardSize))
        {
            DrawCircle(origin + new Vector2(star.X * step, star.Y * step), MathF.Max(3f, step * 0.055f), lineColor);
        }

        if (_hoverPoint is { } hover)
        {
            DrawCircle(
                origin + new Vector2(hover.X * step, hover.Y * step),
                step * 0.23f,
                new Color(1f, 0.88f, 0.46f, 0.24f)
            );
        }

        for (var y = 0; y < BoardSize; y++)
        {
            for (var x = 0; x < BoardSize; x++)
            {
                var stone = _board[x, y];
                if (stone == 0)
                {
                    continue;
                }
                var center = origin + new Vector2(x * step, y * step);
                var radius = step * 0.43f;
                DrawCircle(center + new Vector2(radius * 0.08f, radius * 0.12f), radius, new Color(0, 0, 0, 0.22f));
                DrawStone(center, radius, stone);
            }
        }
    }

    private void DrawStone(Vector2 center, float radius, int stone)
    {
        var texture = stone == 1 ? _blackStoneTexture : _whiteStoneTexture;
        if (texture != null)
        {
            var rect = new Rect2(
                center - new Vector2(radius, radius),
                new Vector2(radius * 2f, radius * 2f)
            );
            DrawTextureRect(texture, rect, false);
            DrawCircle(center, radius, new Color(0, 0, 0, 0.04f));
        }
        else
        {
            var color = stone == 1
                ? new Color(0.035f, 0.033f, 0.03f)
                : new Color(0.92f, 0.89f, 0.82f);
            DrawCircle(center, radius, color);
        }
        DrawCircle(
            center - new Vector2(radius * 0.25f, radius * 0.28f),
            radius * 0.20f,
            new Color(1, 1, 1, stone == 1 ? 0.10f : 0.35f)
        );
    }

    public override void _GuiInput(InputEvent @event)
    {
        if (@event is InputEventMouseMotion)
        {
            _hoverPoint = PointFromLocal(GetLocalMousePosition());
            QueueRedraw();
            return;
        }
        if (@event is InputEventMouseButton button && button.Pressed && button.ButtonIndex == MouseButton.Left)
        {
            var point = PointFromLocal(button.Position);
            if (point is { } boardPoint)
            {
                EmitSignal(SignalName.PointSelected, boardPoint.X, boardPoint.Y);
            }
        }
    }

    private Vector2I? PointFromLocal(Vector2 local)
    {
        var rect = GetRect();
        var side = MathF.Min(rect.Size.X, rect.Size.Y);
        var boardOrigin = new Vector2((rect.Size.X - side) * 0.5f, (rect.Size.Y - side) * 0.5f);
        var padding = side * 0.075f;
        var gridSide = side - padding * 2f;
        var step = BoardSize > 1 ? gridSide / (BoardSize - 1) : gridSide;
        var gridPos = local - boardOrigin - new Vector2(padding, padding);
        var x = Mathf.RoundToInt(gridPos.X / step);
        var y = Mathf.RoundToInt(gridPos.Y / step);
        if (x < 0 || y < 0 || x >= BoardSize || y >= BoardSize)
        {
            return null;
        }
        var snapped = new Vector2(x * step, y * step);
        if (gridPos.DistanceTo(snapped) > step * 0.45f)
        {
            return null;
        }
        return new Vector2I(x, y);
    }

    private void LoadStaticAssets()
    {
        _boardTexture = LoadTexture("res://assets/textures/board-kaya-classic-v1.png");
        _blackStoneTexture = LoadTexture("res://assets/textures/stone-black-traditional-v1.png");
        _whiteStoneTexture = LoadTexture("res://assets/textures/stone-materials-tech-v3.png");
    }

    private static Texture2D? LoadTexture(string path)
    {
        var globalPath = ProjectSettings.GlobalizePath(path);
        if (!File.Exists(globalPath))
        {
            return null;
        }
        var image = Image.LoadFromFile(globalPath);
        return image == null ? null : ImageTexture.CreateFromImage(image);
    }

    private static Vector2I[] StarPoints(int size)
    {
        if (size >= 19)
        {
            return new[]
            {
                new Vector2I(3, 3), new Vector2I(9, 3), new Vector2I(15, 3),
                new Vector2I(3, 9), new Vector2I(9, 9), new Vector2I(15, 9),
                new Vector2I(3, 15), new Vector2I(9, 15), new Vector2I(15, 15),
            };
        }
        if (size >= 13)
        {
            return new[]
            {
                new Vector2I(3, 3), new Vector2I(9, 3), new Vector2I(6, 6),
                new Vector2I(3, 9), new Vector2I(9, 9),
            };
        }
        if (size >= 9)
        {
            return new[]
            {
                new Vector2I(2, 2), new Vector2I(6, 2), new Vector2I(4, 4),
                new Vector2I(2, 6), new Vector2I(6, 6),
            };
        }
        return Array.Empty<Vector2I>();
    }
}
