# Builds the Windows release: a folder with ZombieDice.exe, zipped.
#
# ZombieDice.exe is python.exe from the official embeddable Python package, renamed, so the only
# executable in the release is one signed by the Python Software Foundation (see
# zombiedice_launch.py). Nothing is packed, compressed or self-extracting, which is what makes
# bundlers like PyInstaller trip antivirus heuristics.
#
# Run from the repository root with the same Python version on PATH (it installs numpy for it):
#   pwsh packaging/windows/build.ps1 -Version 1.0.0
param(
    [string]$Version = "dev",
    [string]$OutDir = "dist"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$py = (python -c "import sys; print('%d.%d.%d' % sys.version_info[:3])").Trim()
$tag = (python -c "import sys; print('%d%d' % sys.version_info[:2])").Trim()
$name = "ZombieDice"
$app = Join-Path $OutDir $name
$zip = Join-Path $OutDir "$name-$Version-windows-x64.zip"
if (Test-Path $OutDir) { Remove-Item -Recurse -Force $OutDir }
New-Item -ItemType Directory -Force $app | Out-Null

Write-Host "== Embeddable Python $py"
$embed = Join-Path $OutDir "python-embed.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$py/python-$py-embed-amd64.zip" -OutFile $embed
Expand-Archive $embed -DestinationPath $app
Remove-Item $embed

# The signed python.exe becomes the game's exe; the windowless variant and the stock path file go.
Move-Item (Join-Path $app "python.exe") (Join-Path $app "$name.exe")
Remove-Item (Join-Path $app "pythonw.exe"), (Join-Path $app "python$tag._pth")
# Python reads the ._pth named after its exe: it fixes sys.path and enables site, which runs the .pth below.
@("python$tag.zip", ".", "app", "Lib\site-packages", "import site") |
    Set-Content -Encoding ascii (Join-Path $app "$name._pth")

Write-Host "== numpy"
$site = Join-Path $app "Lib\site-packages"
python -m pip install --disable-pip-version-check --no-compile --only-binary=:all: --target $site "numpy>=1.26"
Get-ChildItem $site -Directory -Filter "*.dist-info" | Out-Null

Write-Host "== game"
$code = Join-Path $app "app"
New-Item -ItemType Directory -Force $code | Out-Null
foreach ($pkg in "zombie", "unicode3d") {
    Copy-Item -Recurse $pkg (Join-Path $code $pkg)
}
Get-ChildItem $code -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Copy-Item "packaging/windows/zombiedice_launch.py" $code
"import zombiedice_launch" | Set-Content -Encoding ascii (Join-Path $site "zombiedice.pth")
(Get-Content "packaging/windows/README.txt" -Raw).Replace("{VERSION}", $Version) |
    Set-Content -Encoding utf8 (Join-Path $app "README.txt")

Write-Host "== signature"
$sig = Get-AuthenticodeSignature (Join-Path $app "$name.exe")
Write-Host "$($sig.Status): $($sig.SignerCertificate.Subject)"
if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "Python Software Foundation") {
    throw "ZombieDice.exe is not validly signed by the Python Software Foundation"
}
# Every other executable file must be signed too, or be a plain library loaded by the signed exe.
Get-ChildItem $app -Recurse -Include *.exe | Where-Object { $_.Name -ne "$name.exe" } | ForEach-Object {
    throw "unexpected executable in the release: $($_.FullName)"
}

Write-Host "== zip"
Compress-Archive -Path $app -DestinationPath $zip
$hash = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
"$hash  $(Split-Path $zip -Leaf)" | Set-Content -Encoding ascii "$zip.sha256"
Write-Host "$zip  sha256 $hash"
