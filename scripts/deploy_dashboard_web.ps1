param(
  [ValidateSet("prod", "dev")]
  [string]$Environment
)

$ErrorActionPreference = "Stop"

$flutter = "C:\Users\pohbo\develop\flutter\bin\flutter.bat"
$firebase = "C:\Users\pohbo\AppData\Roaming\npm\firebase.cmd"

$config = @{
  prod = @{
    HostingTarget = "prod"
  }
  dev = @{
    HostingTarget = "dev"
  }
}

if (-not $Environment) {
  $branch = (& git branch --show-current).Trim()
  $Environment = switch ($branch) {
    "main" { "prod" }
    "developer" { "dev" }
    default {
      throw "Unsupported branch '$branch'. Pass -Environment prod or -Environment dev explicitly."
    }
  }
}

$selected = $config[$Environment]

& $flutter build web --release --pwa-strategy=none --no-wasm-dry-run
& $firebase deploy --only "hosting:$($selected.HostingTarget)" --project budget-bot-123
