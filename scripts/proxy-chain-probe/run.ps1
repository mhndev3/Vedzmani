# Reproducible LOCAL probe of the client-IP chain: real nginx config files -> header-echo "backend" -> real get_client_ip().
# Disposable: private docker network + containers prefixed a06-probe-, no published ports, no volumes, no VPS, no
# Cloudflare. It proves what OUR configs do with forwarded headers; it does NOT prove the production network path.
#
#   powershell -File scripts\proxy-chain-probe\run.ps1 [-ProdConf <path to nginx/prod.conf>] [-ProdRealip <path>]
#
# nginx/prod.conf lives on the (unmerged) infra branch; point -ProdConf at a checkout that has it, or omit it to
# probe only nginx/default.conf.
param(
    [string]$ProdConf = '',
    [string]$ProdRealip = ''
)
$ErrorActionPreference = 'Continue'
$probe = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $probe '..\..')).Path
$backend = Join-Path $repo 'backend'
$py = Join-Path $backend '.venv\Scripts\python.exe'
$work = Join-Path $env:TEMP '_a06_probe_work'
$net = 'a06-probe-net'; $subnet = '172.29.250.0/24'
$ipTrusted = '172.29.250.10'; $ipOther = '172.29.250.20'
$containers = @('a06-probe-echo', 'a06-probe-nginx-default', 'a06-probe-nginx-prod-empty', 'a06-probe-nginx-prod-trust')

function Cleanup {
    docker rm -f @containers 2>$null | Out-Null
    docker network rm $net 2>$null | Out-Null
    if (Test-Path $work) { Remove-Item $work -Recurse -Force }
}

function Start-Nginx($name, [string[]]$mounts) {
    $args = @('run', '-d', '--name', $name, '--network', $net)
    foreach ($m in $mounts) { $args += @('-v', $m) }
    $args += 'nginx:alpine'
    docker @args | Out-Null
    Start-Sleep -Seconds 2
    $t = docker exec $name nginx -t 2>&1
    Write-Output ("  [{0}] nginx -t: {1}" -f $name, (($t | Select-Object -Last 1) -replace '\s+', ' '))
}

function Probe($label, $nginx, $scheme, $clientIp, [string[]]$headers, $expected) {
    $cargs = @('run', '--rm', '--network', $net, '--ip', $clientIp, '-v', "$probe\client.js:/client.js:ro", 'node:24-alpine', 'node', '/client.js', $scheme, $nginx) + $headers
    $line = (docker @cargs 2>&1 | Select-Object -Last 1)
    try { $r = $line | ConvertFrom-Json } catch { Write-Output "  $label : unparsable ($line)"; return }
    if ($r.error -or -not $r.echo) { Write-Output "  $label : $line"; return }
    $xff = $r.echo.headers.'x-forwarded-for'
    $env:DJANGO_SETTINGS_MODULE = 'config.settings.test'
    $env:AUTH_TRUSTED_PROXY_COUNT = '1'
    Push-Location $backend  # settings module is importable only from backend/
    $derived = & $py -c "import django; django.setup(); from django.conf import settings; from django.test import RequestFactory; from apps.accounts.ratelimit import get_client_ip; print(get_client_ip(RequestFactory().get('/', REMOTE_ADDR='$($r.echo.peer)', HTTP_X_FORWARDED_FOR='$xff')))" 2>&1 | Select-Object -Last 1
    Pop-Location
    $verdict = if ($derived -eq $expected) { 'OK' } else { 'DIFFERENT' }
    Write-Output ("  {0,-34} client={1,-13} XFF-at-backend={2,-34} derived={3,-15} wanted={4,-15} {5}" -f $label, $clientIp, $xff, $derived, $expected, $verdict)
}

Cleanup
New-Item -ItemType Directory -Force $work | Out-Null
try {
    docker network create --subnet $subnet $net | Out-Null
    docker run -d --name a06-probe-echo --network $net --network-alias backend --network-alias frontend -v "$probe\echo.js:/echo.js:ro" node:24-alpine node /echo.js | Out-Null

    Write-Output '== nginx/default.conf (this repo, unmodified): XFF = $proxy_add_x_forwarded_for, no real-ip module'
    Start-Nginx 'a06-probe-nginx-default' @("$repo\nginx\default.conf:/etc/nginx/conf.d/default.conf:ro")
    Probe 'A1 plain client'                'a06-probe-nginx-default' 'http' $ipOther @() $ipOther
    Probe 'A2 spoofed XFF'                 'a06-probe-nginx-default' 'http' $ipOther @('X-Forwarded-For=9.9.9.9') $ipOther
    Probe 'A3 spoofed XFF chain + CF hdr'  'a06-probe-nginx-default' 'http' $ipOther @('X-Forwarded-For=9.9.9.9,8.8.8.8', 'CF-Connecting-IP=1.2.3.4') $ipOther

    if ($ProdConf -and (Test-Path $ProdConf)) {
        docker run --rm -v "${work}:/out" alpine/openssl req -x509 -newkey rsa:2048 -nodes -keyout /out/origin.key -out /out/origin.pem -days 1 -subj '/CN=vedzmani.ir' 2>&1 | Out-Null
        $emptyRealip = if ($ProdRealip -and (Test-Path $ProdRealip)) { $ProdRealip } else { Join-Path $work 'realip-empty.conf'; '' | Set-Content (Join-Path $work 'realip-empty.conf') }
        $trustFile = Join-Path $work 'realip-trust.conf'
        "set_real_ip_from $ipTrusted;`nreal_ip_header CF-Connecting-IP;`nreal_ip_recursive off;" | Set-Content $trustFile
        $certs = @("$work\origin.pem:/etc/nginx/certs/origin.pem:ro", "$work\origin.key:/etc/nginx/certs/origin.key:ro")

        Write-Output "== nginx/prod.conf (unmodified), cloudflare-realip.conf as committed (no ranges): XFF = `$remote_addr"
        Start-Nginx 'a06-probe-nginx-prod-empty' (@("${ProdConf}:/etc/nginx/conf.d/default.conf:ro", "${emptyRealip}:/etc/nginx/cloudflare-realip.conf:ro") + $certs)
        Probe 'B1 spoofed XFF + CF hdr, no ranges' 'a06-probe-nginx-prod-empty' 'https' $ipOther @('X-Forwarded-For=9.9.9.9', 'CF-Connecting-IP=1.2.3.4') $ipOther

        Write-Output "== nginx/prod.conf (unmodified) + a TEST real-ip file that trusts only $ipTrusted (stands in for the Cloudflare ranges)"
        Start-Nginx 'a06-probe-nginx-prod-trust' (@("${ProdConf}:/etc/nginx/conf.d/default.conf:ro", "${trustFile}:/etc/nginx/cloudflare-realip.conf:ro") + $certs)
        Probe 'B2 trusted edge, CF hdr + spoof XFF' 'a06-probe-nginx-prod-trust' 'https' $ipTrusted @('CF-Connecting-IP=198.51.100.77', 'X-Forwarded-For=9.9.9.9') '198.51.100.77'
        Probe 'B3 UNtrusted peer sends CF hdr'      'a06-probe-nginx-prod-trust' 'https' $ipOther @('CF-Connecting-IP=198.51.100.77', 'X-Forwarded-For=9.9.9.9') $ipOther
        Probe 'B4 trusted edge, no CF hdr'          'a06-probe-nginx-prod-trust' 'https' $ipTrusted @('X-Forwarded-For=9.9.9.9') $ipTrusted
    } else {
        Write-Output '== nginx/prod.conf not probed (pass -ProdConf <path>)'
    }
}
finally {
    Cleanup
    Write-Output '== cleaned up: probe containers, network and temp files removed'
}
