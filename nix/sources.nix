{ fetchFromGitHub, fetchurl }:
{
  legacySource = fetchFromGitHub {
    owner = "imagej";
    repo = "ImageJ";
    rev = "03382be1a0b650010b077102b5e5b20eaa6a8967";
    hash = "sha256-5O4oWxCPix3fUOtbI6Zllu/n0hwoU0p1eP+9EJkjYak=";
  };
  updater = fetchurl {
    url = "https://sites.imagej.net/Java-8/jars/imagej-updater-1.1.2.jar-20250512142246";
    hash = "sha256-GcgQNR0YNmuOn/1rSmlmN7fh6gfSOEQ5zGoY7uYGK8U=";
  };
  updaterSource = fetchFromGitHub {
    owner = "imagej";
    repo = "imagej-updater";
    rev = "bf9be26fc92ccb9201f62514222039a049d9f4ec";
    hash = "sha256-Cjxhn1oICZJhImDg45gN5WRGYqU43JgEYrxMDnQdY44=";
  };
  launcherSource = fetchFromGitHub {
    owner = "imagej";
    repo = "imagej-launcher";
    rev = "2850e717211e86cb5d2a1a50a0380495d3966f81";
    hash = "sha256-M4G6EjiK2T5Gilwowzi+mnUXU4e8L42YHoR1yQKku8w=";
  };
}
