$env:HOSTNAME = "127.0.0.1"
$script = "npm run dev"
Set-Location "$PSScriptRoot\..\frontend"
npm run dev