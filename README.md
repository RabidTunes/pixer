# Pixer (v0.95 pre-release, fixed a lot of bugs, should work better now but still checking for bugs and corner cases)

[Click here to go to the latest release and download the zip for the latest version](https://github.com/RabidTunes/pixer/releases/tag/0.95)

This is a Blender Addon that makes your textures' model ✨pixel perfect✨

This means that if you apply a pixel art texture the pixels will be of a consistent size across your model.

# HOW TO INSTALL

Download the zip file and install it from preferences. <sub><sup>(I'm too lazy to explain this but it is the typical procedure just install it as any other addon)</sup></sub>

# HOW TO USE

- First make a 3D model!

- Switch to ortographic view and make sure all your vertices are aligned to the grid. You can press SHIFT + S -> snap to grid to do this.

- (OPTIONAL) If you feel that this snap to grid crunches your model, you can change the grid size (TODO ADD IMAGE WHERE TO CHANGE THIS) then snap to grid again

- Now go to Pixer addon panel on 3D view in edit mode and input the [number of pixels per 3D unit](https://github.com/RabidTunes/pixeltexturizer/blob/main/FAQ.md). It usually is 10 if you skipped the optional step, but this is the grid size if you modified it.

- Assign a squared texture to the model and input the texture size (must be a square texture)

- (Optional) Mark "Selection only" if you want to pixelize only selected faces. Otherwise, pixer will pixelize every face

- SUPER IMPORTANT APPLY ALL TRANSFORMS!. Pixer uses the edge length for its calculations, if you make some modifications on Object mode like scale, the edge lengths will not be correct and your model won't be pixelated correctly! (i got very frustrated developing this because this apply transforms thing got me thinking i had a massive bug, but in the end it was only the transform)

- Press "Pixelize" button

It is very important that you adjust all the vertices to the grid (edit mode > enter ortographic view > press shift + S > selected to grid)
If vertices are not adjusted to the grid, I'm not sure what would happen, it probably might work anyways but I haven't tested what happens then 👀

Video explanation: Coming 🔜
