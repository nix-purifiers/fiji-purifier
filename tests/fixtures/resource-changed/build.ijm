length = 4;
newImage("source", "8-bit black", 12, 12, 1);
for (y=4; y<=6; y++)
  for (x=4; x<4+length; x++) setPixel(x,y,255);
run("Morphological Filters", "operation=Dilation element=Square radius=1");
File.makeDirectory(getArgument());
saveAs("Tiff", getArgument()+"/dilated.tif");
