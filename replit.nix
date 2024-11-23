{ pkgs }: {
  deps = [
    pkgs.gdb
    pkgs.gir-rs
    pkgs.replitPackages.prybar-python310
    pkgs.replitPackages.stderred
  ];
}