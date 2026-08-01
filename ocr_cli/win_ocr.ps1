param(
    [Parameter(Mandatory=$true)][string]$ImagePath,
    [string]$OutFile = ""
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait()
    $netTask.Result
}

$lang = New-Object Windows.Globalization.Language('zh-Hant-TW')
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) {
    Write-Error "zh-Hant OCR engine unavailable"
    exit 1
}

$ImagePath = [System.IO.Path]::GetFullPath($ImagePath)
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])

$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

$sb = New-Object System.Text.StringBuilder
foreach ($line in $result.Lines) {
    $parts = @()
    foreach ($wd in $line.Words) {
        $r = $wd.BoundingRect
        $parts += "[$($wd.Text)@$([int]$r.X),$([int]$r.Y),$([int]$r.Width),$([int]$r.Height)]"
    }
    $null = $sb.AppendLine(($parts -join ' '))
}

if ($OutFile -ne "") {
    $OutFile = [System.IO.Path]::GetFullPath($OutFile)
    [System.IO.File]::WriteAllText($OutFile, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
} else {
    $sb.ToString()
}
