using Godot;
using System.Collections.Generic;
using System.IO;

public partial class ToolbarStrip : HBoxContainer
{
    private static readonly (string Icon, string Label, bool Disabled)[] Items =
    {
        ("setup", "开始", false),
        ("skill", "Rogue", false),
        ("wiki", "Wiki", false),
        ("pass", "虚手", true),
        ("undo", "悔棋", true),
        ("score", "计算", true),
        ("territory-on", "形势", false),
        ("resign", "认输", true),
        ("settings", "设置", false),
    };
    private readonly List<(Button Button, string Label)> _buttons = new();

    public override void _Ready()
    {
        AddThemeConstantOverride("separation", 8);
        foreach (var (icon, label, disabled) in Items)
        {
            var button = CreateButton(icon, label, disabled);
            _buttons.Add((button, label));
            AddChild(button);
        }
    }

    public void FitToWidth(float width)
    {
        var compact = width < 620f;
        var separation = compact ? 4 : 8;
        AddThemeConstantOverride("separation", separation);
        var buttonWidth = compact
            ? Mathf.Max(32f, (width - (Items.Length - 1) * separation) / Items.Length)
            : 78f;
        foreach (var (button, label) in _buttons)
        {
            button.Text = compact ? "" : label;
            button.CustomMinimumSize = new Vector2(buttonWidth, compact ? 46f : 54f);
        }
    }

    private static Button CreateButton(string iconName, string label, bool disabled)
    {
        return new Button
        {
            Text = label,
            Icon = LoadTexture($"res://assets/icons/toolbar-tech/{iconName}.png"),
            Disabled = disabled,
            ExpandIcon = true,
            CustomMinimumSize = new Vector2(78, 54),
            TooltipText = label,
        };
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
}
