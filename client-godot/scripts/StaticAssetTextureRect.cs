using Godot;
using System.IO;

public partial class StaticAssetTextureRect : TextureRect
{
    [Export]
    public string AssetPath { get; set; } = "";

    public override void _Ready()
    {
        ExpandMode = ExpandModeEnum.IgnoreSize;
        StretchMode = StretchModeEnum.KeepAspectCovered;
        var path = ProjectSettings.GlobalizePath(AssetPath);
        if (!File.Exists(path))
        {
            return;
        }
        var image = Image.LoadFromFile(path);
        if (image != null)
        {
            Texture = ImageTexture.CreateFromImage(image);
        }
    }

}
