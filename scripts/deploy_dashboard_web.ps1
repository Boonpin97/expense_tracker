param(
  [ValidateSet("prod", "dev")]
  [string]$Environment,

  [string]$ProjectId = $env:FIREBASE_PROJECT_ID
)

$ErrorActionPreference = "Stop"

$npm = "C:\Program Files\nodejs\npm.cmd"
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

if (-not $ProjectId) {
  throw "ProjectId is required. Pass -ProjectId <firebase-project-id> or set FIREBASE_PROJECT_ID."
}

$selected = $config[$Environment]

& $npm run build
& $firebase deploy --only "hosting:$($selected.HostingTarget)" --project $ProjectId
