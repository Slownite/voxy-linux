{
  description = "voxy — local offline voice dictation for Linux";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        py = pkgs.python313;

        cudaPkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
            cudaSupport = true;
          };
        };
        cudaPy = cudaPkgs.python313;

        # Display-server-agnostic Python deps.
        # Quoted attrs are required for names containing hyphens.
        corePythonDeps = ps:
          (with ps; [
            sounddevice
            evdev
            numpy
            pynput
            mypy
            pytest
            ruff
            setuptools
            build
            twine
          ])
          ++ [ ps."faster-whisper" ps."dbus-next" ];

        # Wayland-specific deps (mirrors pyproject wayland extra).
        # Requires system gtk4 + gtk4-layer-shell.
        waylandPythonDeps = ps: with ps; [ pygobject3 pycairo ];
        waylandSystemDeps = with pkgs; [ wl-clipboard ydotool gtk4 gtk4-layer-shell ];

        # X11-specific deps (mirrors pyproject x11 extra).
        x11PythonDeps = ps: with ps; [ tkinter xlib pycairo ];
        x11SystemDeps = with pkgs; [ xclip xdotool xprop ];

        mkVoxy = pythonInterp: extraPythonDeps: extraSystemDeps:
          pythonInterp.pkgs.buildPythonApplication {
            pname = "voxy-linux";
            version = "0.1.0";
            src = ./.;
            format = "pyproject";

            nativeBuildInputs = with pythonInterp.pkgs; [ setuptools ];
            propagatedBuildInputs =
              (corePythonDeps pythonInterp.pkgs)
              ++ (extraPythonDeps pythonInterp.pkgs)
              ++ extraSystemDeps;
          };

      in
      {
        packages.default = mkVoxy py waylandPythonDeps waylandSystemDeps;
        packages.x11 = mkVoxy py x11PythonDeps x11SystemDeps;

        devShells.default = pkgs.mkShell {
          packages =
            [ (py.withPackages (ps: corePythonDeps ps ++ waylandPythonDeps ps)) ]
            ++ waylandSystemDeps;

          shellHook = ''
            echo "voxy wayland dev — $(python --version)"
          '';
        };

        devShells.x11 = pkgs.mkShell {
          packages =
            [ (py.withPackages (ps: corePythonDeps ps ++ x11PythonDeps ps)) ]
            ++ x11SystemDeps;

          shellHook = ''
            echo "voxy x11 dev — $(python --version)"
          '';
        };

        devShells.cuda = cudaPkgs.mkShell {
          packages =
            [ (cudaPy.withPackages (ps: corePythonDeps ps ++ waylandPythonDeps ps)) ]
            ++ waylandSystemDeps;

          shellHook = ''
            echo "voxy cuda dev — $(python --version)"
          '';
        };
      }
    ))
    // {
      nixosModules.voxy = import ./nixos-module.nix { inherit self; };
    };
}
