using Godot;
using System;
using System.Collections.Generic;
using System.Text.Json;

public partial class Main : Control
{
    private const string GameId = "godot-local";
    private const float HeaderHeight = 72f;
    private const float CommandDeckHeight = 108f;
    private const float ToolbarHeight = 68f;
    private const float ShellGap = 18f;
    private const float DrawerWidth = 330f;

    private RuntimeWorker _worker = null!;
    private BoardView _board = null!;
    private Label _status = null!;
    private Control _header = null!;
    private Control _commandDeck = null!;
    private Control _boardContainer = null!;
    private Control _settingsDrawer = null!;
    private Control _toolbar = null!;
    private Control _cardTray = null!;
    private Control _statusCards = null!;
    private Control _quickActions = null!;
    private Control _languageLabel = null!;
    private Label _hudMode = null!;
    private Label _hudMove = null!;
    private Label _hudTurn = null!;
    private Label _hudCard = null!;
    private Label _hudEngine = null!;

    public override void _Ready()
    {
        _worker = GetNode<RuntimeWorker>("RuntimeWorker");
        _header = GetNode<Control>("HeaderBar");
        _commandDeck = GetNode<Control>("CommandDeck");
        _boardContainer = GetNode<Control>("BoardContainer");
        _settingsDrawer = GetNode<Control>("SettingsDrawer");
        _toolbar = GetNode<Control>("BoardContainer/MainToolbar");
        _cardTray = GetNode<Control>("BoardContainer/CardIconTray");
        _statusCards = GetNode<Control>("CommandDeck/StatusCards");
        _quickActions = GetNode<Control>("CommandDeck/QuickActions");
        _languageLabel = GetNode<Control>("CommandDeck/LanguageLabel");
        _board = GetNode<BoardView>("BoardContainer/BoardView");
        _status = GetNode<Label>("HeaderBar/StatusText");
        _hudMode = GetNode<Label>("BoardContainer/MatchHud/HudMode");
        _hudMove = GetNode<Label>("BoardContainer/MatchHud/HudMove");
        _hudTurn = GetNode<Label>("BoardContainer/MatchHud/HudTurn");
        _hudCard = GetNode<Label>("BoardContainer/MatchHud/HudCard");
        _hudEngine = GetNode<Label>("BoardContainer/MatchHud/HudEngine");
        _board.PointSelected += OnPointSelected;
        ApplyResponsiveLayout();
        CallDeferred(nameof(StartLocalGame));
    }

    public override void _Notification(int what)
    {
        if (what == NotificationResized)
        {
            ApplyResponsiveLayout();
        }
    }

    private void StartLocalGame()
    {
        try
        {
            _status.Text = "对局准备中";
            _hudMode.Text = "准备对局";
            _hudTurn.Text = "待开始";
            _hudCard.Text = "无卡牌";
            _hudEngine.Text = "正在加载模型与同步棋盘…";
            _worker.Request("get_status", new Dictionary<string, object?>());
            var response = _worker.SendAction(new Dictionary<string, object?>
            {
                ["game_id"] = GameId,
                ["action"] = "new_game",
                ["size"] = 9,
                ["komi"] = 6.5,
                ["two_player"] = true,
                ["player_color"] = "B",
            });
            ApplyResponse(response);
            _status.Text = "本地运行时已就绪";
            _hudEngine.Text = "AI 待命";
        }
        catch (Exception exc)
        {
            _status.Text = $"运行时启动失败：{exc.Message}";
            GD.PrintErr(exc);
        }
    }

    private void OnPointSelected(int x, int y)
    {
        try
        {
            var response = _worker.SendAction(new Dictionary<string, object?>
            {
                ["game_id"] = GameId,
                ["action"] = "play",
                ["x"] = x,
                ["y"] = y,
            });
            ApplyResponse(response);
        }
        catch (Exception exc)
        {
            _status.Text = $"落子失败：{exc.Message}";
            GD.PrintErr(exc);
        }
    }

    private void ApplyResponse(string responseJson)
    {
        using var document = JsonDocument.Parse(responseJson);
        var root = document.RootElement;
        if (root.TryGetProperty("ok", out var okElement) && !okElement.GetBoolean())
        {
            _status.Text = root.TryGetProperty("error", out var error)
                ? error.GetString() ?? "Runtime error"
                : "Runtime error";
            return;
        }
        if (!root.TryGetProperty("events", out var events) || events.ValueKind != JsonValueKind.Array)
        {
            return;
        }

        foreach (var item in events.EnumerateArray())
        {
            if (!item.TryGetProperty("type", out var typeElement))
            {
                continue;
            }
            var type = typeElement.GetString();
            if (type == "error")
            {
                _status.Text = item.TryGetProperty("message", out var message)
                    ? message.GetString() ?? "Runtime error"
                    : "Runtime error";
                continue;
            }
            if ((type == "game_start" || type == "game_state") && item.TryGetProperty("board", out var boardElement))
            {
                _board.SetBoard(ParseBoard(boardElement));
                var moveNumber = item.TryGetProperty("move_number", out var move)
                    ? move.GetInt32()
                    : 0;
                var currentPlayer = item.TryGetProperty("current_player", out var player)
                    ? player.GetString()
                    : "?";
                _status.Text = "对局进行中";
                _hudMode.Text = "对局";
                _hudMove.Text = moveNumber.ToString();
                _hudTurn.Text = currentPlayer == "B" ? "黑棋行棋" : "白棋行棋";
            }
        }
    }

    private void ApplyResponsiveLayout()
    {
        var viewport = GetViewportRect().Size;
        var margin = viewport.X < 760 ? 12f : 24f;
        var wide = viewport.X >= 1180f;
        var drawerWidth = wide ? DrawerWidth : 0f;
        var contentTop = HeaderHeight + CommandDeckHeight + margin;
        var contentHeight = Mathf.Max(360f, viewport.Y - contentTop - margin);
        var maxBoardWidth = viewport.X - margin * 2f - drawerWidth - (wide ? ShellGap : 0f);
        var maxBoardHeight = contentHeight - ToolbarHeight - ShellGap * 2f;
        var boardSide = Mathf.Clamp(Mathf.Min(maxBoardWidth, maxBoardHeight), 320f, 900f);
        var boardBlockWidth = boardSide;
        var totalWidth = boardBlockWidth + (wide ? ShellGap + drawerWidth : 0f);
        var left = Mathf.Max(margin, (viewport.X - totalWidth) * 0.5f);
        var boardTop = contentTop + Mathf.Max(0f, (contentHeight - boardSide - ToolbarHeight - ShellGap) * 0.5f);

        _header.Position = Vector2.Zero;
        _header.Size = new Vector2(viewport.X, HeaderHeight);

        _commandDeck.Position = new Vector2(margin, HeaderHeight);
        _commandDeck.Size = new Vector2(viewport.X - margin * 2f, CommandDeckHeight - 8f);
        _statusCards.Visible = viewport.X >= 980f;
        _quickActions.Visible = viewport.X >= 720f;
        _languageLabel.Visible = viewport.X >= 820f;

        _boardContainer.Position = new Vector2(left, boardTop);
        _boardContainer.Size = new Vector2(boardSide, boardSide + ToolbarHeight + ShellGap);

        _board.Position = new Vector2(0f, 0f);
        _board.Size = new Vector2(boardSide, boardSide);

        _toolbar.Position = new Vector2(0f, boardSide + ShellGap);
        _toolbar.Size = new Vector2(boardSide, ToolbarHeight);
        if (_toolbar is ToolbarStrip toolbarStrip)
        {
            toolbarStrip.FitToWidth(boardSide);
        }

        _cardTray.Visible = boardSide >= 460f;
        _cardTray.Position = new Vector2(Mathf.Max(0f, boardSide - 256f), 14f);
        _cardTray.Size = new Vector2(256f, 76f);

        _settingsDrawer.Visible = wide;
        if (wide)
        {
            _settingsDrawer.Position = new Vector2(left + boardBlockWidth + ShellGap, boardTop);
            _settingsDrawer.Size = new Vector2(drawerWidth, Mathf.Min(contentHeight, boardSide + ToolbarHeight + ShellGap));
        }
    }

    private static int[][] ParseBoard(JsonElement boardElement)
    {
        var rows = new List<int[]>();
        foreach (var rowElement in boardElement.EnumerateArray())
        {
            var row = new List<int>();
            foreach (var cell in rowElement.EnumerateArray())
            {
                row.Add(cell.GetInt32());
            }
            rows.Add(row.ToArray());
        }
        return rows.ToArray();
    }
}
