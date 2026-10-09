param(
    [Parameter(Mandatory = $true)][string]$TextPath,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Speech
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voiceName = "Microsoft Kangkang"
    $voice = @($speaker.GetInstalledVoices() | Where-Object {
        $_.Enabled -and $_.VoiceInfo.Name -eq $voiceName -and
        $_.VoiceInfo.Culture.Name -eq "zh-CN" -and
        $_.VoiceInfo.Gender -eq [System.Speech.Synthesis.VoiceGender]::Male
    })
    if ($voice.Count -ne 1) {
        throw "Required enabled zh-CN male voice '$voiceName' not found; no voice substitution allowed."
    }
    $text = [System.IO.File]::ReadAllText($TextPath, [System.Text.Encoding]::UTF8)
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "Narration text is empty: $TextPath"
    }
    if ([System.IO.File]::Exists($OutputPath)) {
        throw "Refusing to overwrite a narration take: $OutputPath"
    }
    $speaker.SelectVoice($voiceName)
    $speaker.Rate = -1
    $speaker.Volume = 100
    $format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(
        48000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono
    )
    $speaker.SetOutputToWaveFile($OutputPath, $format)
    $speaker.Speak($text)
    $speaker.SetOutputToNull()
    @{
        voice = $speaker.Voice.Name
        culture = $speaker.Voice.Culture.Name
        rate = $speaker.Rate
        synthetic = $true
    } | ConvertTo-Json -Compress
}
finally {
    $speaker.Dispose()
}
