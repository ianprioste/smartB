#!/usr/bin/env pwsh
<#
.SYNOPSIS
    One-command deploy: merge dev -> production and push to trigger automated deployment
.DESCRIPTION
    This script:
    1. Stashes any uncommitted changes in current branch
    2. Checks out production
    3. Merges dev into production
    4. Pushes to origin/production (triggers GitHub Actions auto-deploy)
    5. Returns to dev branch
.EXAMPLE
    .\publish.ps1
#>

param(
    [switch]$NoReturn = $false  # If set, stays on production branch instead of returning to original
)

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message, [string]$Type = "Info")
    $colors = @{
        "✓" = "Green"
        "✗" = "Red"
        "→" = "Cyan"
        "⚠" = "Yellow"
    }
    $symbol = @{
        "Info" = "→"
        "Success" = "✓"
        "Error" = "✗"
        "Warning" = "⚠"
    }
    Write-Host "$($symbol[$Type]) $Message" -ForegroundColor $colors[$symbol[$Type]]
}

try {
    # Current branch
    $currentBranch = git rev-parse --abbrev-ref HEAD
    Write-Status "Current branch: $currentBranch" "Info"

    # Stash any uncommitted changes
    $status = git status --porcelain
    if ($status) {
        Write-Status "Stashing uncommitted changes..." "Info"
        git stash
        $hasStash = $true
    }

    # Checkout production
    Write-Status "Switching to production branch..." "Info"
    git checkout production
    
    # Pull latest production
    Write-Status "Pulling latest changes..." "Info"
    git pull origin production
    
    # Merge dev
    Write-Status "Merging dev into production..." "Info"
    git merge dev --no-edit
    
    # Push to origin/production (triggers GitHub Actions)
    Write-Status "Pushing to origin/production (deploying to production)..." "Info"
    git push origin production
    
    Write-Status "✓ Deploy pushed successfully!" "Success"
    Write-Host ""
    Write-Host "GitHub Actions will now automatically:" -ForegroundColor Cyan
    Write-Host "  1. Run production pipeline"
    Write-Host "  2. SSH into VPS"
    Write-Host "  3. Update backend/frontend services"
    Write-Host "  4. Verify health checks"
    Write-Host ""
    Write-Status "Monitor progress: gh run list --workflow 'Deploy Production (production)' --limit 5" "Info"
    Write-Host ""
    
    # Return to original branch if requested
    if (-not $NoReturn -and $currentBranch -ne "production") {
        Write-Status "Returning to $currentBranch branch..." "Info"
        git checkout $currentBranch
        
        if ($hasStash) {
            Write-Status "Restoring stashed changes..." "Info"
            git stash pop
        }
    }
    
    Write-Status "Done!" "Success"
}
catch {
    Write-Status "Error: $_" "Error"
    # Try to restore original state
    if ($currentBranch -ne "production") {
        Write-Status "Attempting to restore original branch..." "Warning"
        git checkout $currentBranch -ErrorAction SilentlyContinue
        if ($hasStash) {
            git stash pop -ErrorAction SilentlyContinue
        }
    }
    exit 1
}
