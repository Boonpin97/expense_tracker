param(
  [string]$ClientDir = "lovable/dist/client"
)

$ErrorActionPreference = "Stop"

$clientPath = Join-Path (Get-Location) $ClientDir
$assetsPath = Join-Path $clientPath "assets"

if (-not (Test-Path $assetsPath)) {
  throw "Assets directory not found: $assetsPath"
}

$entryScript = Get-ChildItem $assetsPath -Filter "index-*.js" |
  Where-Object {
    Select-String -Path $_.FullName -Pattern "hydrateRoot\(document" -Quiet
  } |
  Select-Object -First 1

if (-not $entryScript) {
  throw "Unable to find Lovable entry script in $assetsPath"
}

$stylesheet = Get-ChildItem $assetsPath -Filter "styles-*.css" | Select-Object -First 1

if (-not $stylesheet) {
  throw "Unable to find Lovable stylesheet in $assetsPath"
}

$html = @"
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Expense Monitor</title>
    <meta name="description" content="Expense Bot dashboard for analytics, transactions, categories, and budgets.">
    <link rel="stylesheet" href="/assets/$($stylesheet.Name)">
  </head>
  <body>
    <script type="module" src="/assets/$($entryScript.Name)"></script>
  </body>
</html>
"@

$indexPath = Join-Path $clientPath "index.html"
Set-Content -LiteralPath $indexPath -Value $html -NoNewline

Write-Output "Generated $indexPath"
