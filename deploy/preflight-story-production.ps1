[CmdletBinding()]
param(
    [string]$MainBaseUrl = "https://ynexai.cn",
    [string]$StoryBaseUrl = "http://127.0.0.1:8000",
    [string]$StoryWebDir = "/srv/ynex/story-web",
    [string]$StoryDownloadsDir = "/srv/ynex/story-downloads",
    [switch]$SkipNetwork,
    [switch]$SkipFilesystem
)

$ErrorActionPreference = "Stop"
$failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure([string]$Message) {
    $failures.Add($Message)
}

function Require-Secret([string]$Name) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value) -or $value.Length -lt 32) {
        Add-Failure "$Name must be configured with at least 32 characters"
    }
}

function Test-JsonPricing {
    $raw = [Environment]::GetEnvironmentVariable("STORY_CREDIT_PRICING_JSON")
    if ([string]::IsNullOrWhiteSpace($raw)) {
        Add-Failure "STORY_CREDIT_PRICING_JSON is missing"
        return
    }
    try {
        $pricing = $raw | ConvertFrom-Json
    }
    catch {
        Add-Failure "STORY_CREDIT_PRICING_JSON is not valid JSON"
        return
    }
    foreach ($operation in @("text2img", "tts", "video_compose", "character_generate")) {
        $property = $pricing.PSObject.Properties[$operation]
        $price = if ($property) { $property.Value } else { $null }
        if ($price -isnot [int] -or $price -le 0) {
            Add-Failure "reviewed positive integer price is missing for $operation"
        }
    }
    if ($pricing.PSObject.Properties["chat"]) {
        Add-Failure "chat must be metered by the Y·NEX model gateway, not fixed Story pricing"
    }
}

function Test-Health([string]$Name, [string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
            Add-Failure "$Name health check returned HTTP $($response.StatusCode)"
        }
    }
    catch {
        Add-Failure "$Name health check failed"
    }
}

if ([Environment]::GetEnvironmentVariable("BILLING_MODE") -ne "jarvis") {
    Add-Failure "BILLING_MODE must be jarvis"
}
Require-Secret "STORY_SSO_SECRET"
Require-Secret "STORY_SERVICE_TOKEN"
Require-Secret "YNEX_SSO_SECRET"
Require-Secret "YNEX_BILLING_SERVICE_TOKEN"

$storySso = [Environment]::GetEnvironmentVariable("STORY_SSO_SECRET")
$ynexSso = [Environment]::GetEnvironmentVariable("YNEX_SSO_SECRET")
if ($storySso -and $ynexSso -and $storySso -cne $ynexSso) {
    Add-Failure "main-site and Story SSO secrets do not match"
}
$storyService = [Environment]::GetEnvironmentVariable("STORY_SERVICE_TOKEN")
$ynexService = [Environment]::GetEnvironmentVariable("YNEX_BILLING_SERVICE_TOKEN")
if ($storyService -and $ynexService -and $storyService -cne $ynexService) {
    Add-Failure "main-site and Story billing service tokens do not match"
}

Test-JsonPricing

if (-not $SkipFilesystem) {
    if (-not (Test-Path -LiteralPath (Join-Path $StoryWebDir "index.html") -PathType Leaf)) {
        Add-Failure "Story web index.html is missing"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $StoryDownloadsDir "index.html") -PathType Leaf)) {
        Add-Failure "Story download index.html is missing"
    }
}

if (-not $SkipNetwork) {
    Test-Health "Y·NEX main site" "$($MainBaseUrl.TrimEnd('/'))/health"
    Test-Health "Story API" "$($StoryBaseUrl.TrimEnd('/'))/health"
}

if ($failures.Count -gt 0) {
    Write-Error ("Story production preflight failed:`n- " + ($failures -join "`n- "))
    exit 1
}

Write-Output "Story production preflight passed"
