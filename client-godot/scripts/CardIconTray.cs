using Godot;
using System.IO;

public partial class CardIconTray : HBoxContainer
{
    [Export]
    public string[] CardIds { get; set; } = { "blackhole", "fog", "quickthink" };

    public override void _Ready()
    {
        AddThemeConstantOverride("separation", 12);
        foreach (var cardId in CardIds)
        {
            var path = ProjectSettings.GlobalizePath($"res://assets/icons/cards-tech/{cardId}.png");
            if (!File.Exists(path))
            {
                continue;
            }
            var image = Image.LoadFromFile(path);
            if (image == null)
            {
                continue;
            }
            var icon = new TextureRect
            {
                Texture = ImageTexture.CreateFromImage(image),
                CustomMinimumSize = new Vector2(72, 72),
                ExpandMode = TextureRect.ExpandModeEnum.FitWidthProportional,
                StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                TooltipText = cardId,
            };
            AddChild(icon);
        }
    }
}
