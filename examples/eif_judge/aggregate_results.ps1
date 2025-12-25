$labels = @{
    1="FALSE"; 2="TRUE"; 3="TRUE"; 4="FALSE"; 5="FALSE";
    6="FALSE"; 7="FALSE"; 8="FALSE"; 9="FALSE"; 10="TRUE"
}
$resultsDir = "d:\Downloads\aDrive\GOT\GOT\code\graph-of-thoughts\examples\eif_judge\results"
$dirs = Get-ChildItem -Path $resultsDir -Directory

foreach ($dir in $dirs) {
    $dirName = $dir.Name
    $method = $dirName.Split('_')[1]
    $subdir = Join-Path $dir.FullName $method
    
    if (Test-Path $subdir) {
        $tp=0; $tn=0; $fp=0; $fn=0; $totalCost=0
        for ($i=1; $i -le 10; $i++) {
            $file = Join-Path $subdir "$i.json"
            if (Test-Path $file) {
                $txt = Get-Content $file -Raw
                if ($txt -match '"problem_solved":\s*\[\s*true') {
                    $solved = $true
                } else {
                    $solved = $false
                }
                
                $cost = 0
                $match = [regex]::Match($txt, '"cost":\s*([\d\.]+)')
                if ($match.Success) {
                    $cost = [double]$match.Groups[1].Value
                }
                
                $totalCost += $cost
                $gt = $labels[$i]
                
                if ($solved) {
                    if ($gt -eq "TRUE") { $tp++ } else { $tn++ }
                } else {
                    if ($gt -eq "TRUE") { $fn++ } else { $fp++ }
                }
            }
        }
        Write-Output "$dirName | TP:$tp TN:$tn FP:$fp FN:$fn | Cost:$totalCost"
    }
}
