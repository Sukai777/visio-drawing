#requires -Version 7.0
param(
    [Parameter(Mandatory=$true)][string]$Model,
    [Parameter(Mandatory=$true)][string]$Output,
    [switch]$TestTransforms
)
$ErrorActionPreference='Stop'
$culture=[Globalization.CultureInfo]::InvariantCulture
function F([double]$n){$n.ToString('R',$culture)}
function Prop($o,[string]$key,$fallback){if($null -ne $o -and $null -ne $o.PSObject.Properties[$key]){return ,($o.$key)}else{return ,$fallback}}
$spec=Get-Content -LiteralPath $Model -Raw -Encoding UTF8 | ConvertFrom-Json
$assetDir=Join-Path (Split-Path -Parent $PSScriptRoot) 'assets'
$catalog=Get-Content -LiteralPath (Join-Path $assetDir 'components.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($spec.version -ne 2 -or -not $spec.source_lock){throw 'Use drawing.py prepare before rendering.'}
foreach($entry in $spec.extra_types.PSObject.Properties){$catalog.components | Add-Member -NotePropertyName $entry.Name -NotePropertyValue $entry.Value -Force}
$Output=[IO.Path]::GetFullPath($Output)
if([IO.Path]::GetExtension($Output) -ne '.vsdx'){throw 'Output must end in .vsdx'}
$outDir=Split-Path -Parent $Output
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stem=Join-Path $outDir ([IO.Path]::GetFileNameWithoutExtension($Output))
if(Test-Path -LiteralPath $Output){Copy-Item -LiteralPath $Output -Destination ($stem+'.backup-'+(Get-Date -Format 'yyyyMMdd-HHmmssfff')+'.vsdx')}
$scale=[double](Prop $spec 'inches_per_unit' 0.015)
$pageHeight=[double]$spec.canvas[1]*$scale
$script:objects=@{};$script:wireRecords=@();$script:componentRecords=@();$script:anchorCount=0
$script:layoutFindings=@();$script:labelRecords=@()
function PX([double]$x){$x*$scale}
function PY([double]$y){$pageHeight-$y*$scale}
function Color([string]$c){if($c -notmatch '^#[0-9a-fA-F]{6}$'){throw "Invalid color $c"};'RGB('+[Convert]::ToInt32($c.Substring(1,2),16)+','+[Convert]::ToInt32($c.Substring(3,2),16)+','+[Convert]::ToInt32($c.Substring(5,2),16)+')'}
function Paint($s,[string]$color,[double]$weight){
    $s.CellsU('LineColor').FormulaU=Color $color
    $s.CellsU('LineWeight').FormulaU=(F $weight)+' pt'
    for($i=1;$i -le $s.Shapes.Count;$i++){Paint $s.Shapes.Item($i) $color $weight}
}
function Set-Fill($s,[string]$color){
    if(-not $s.OneD){$s.CellsU('FillPattern').FormulaU='1';$s.CellsU('FillForegnd').FormulaU=Color $color}
    foreach($child in $s.Shapes){Set-Fill $child $color}
}
function Pin([string]$endpoint){
    $parts=$endpoint.Split('.')
    if($parts.Count -ne 2 -or -not $script:objects.ContainsKey($parts[0])){throw "Unknown endpoint $endpoint"}
    $o=$script:objects[$parts[0]];$p=$o.definition.pins.PSObject.Properties[$parts[1]]
    if($null -eq $p){throw "Unknown pin $endpoint"}
    $row=[int]$p.Value.row
    $cx=$o.shape.CellsSRC(7,$row,0);$cy=$o.shape.CellsSRC(7,$row,1)
    $x=0.0;$y=0.0;$o.shape.XYToPage($cx.ResultIU,$cy.ResultIU,[ref]$x,[ref]$y)
    [pscustomobject]@{shape=$o.shape;cell=$cx;x=$x;y=$y;row=$row;endpoint=$endpoint}
}
function Custom-Shape($item,$def){
    $type=[string]$item.type
    if($type -in @('current_source','voltage_source','ellipse','terminator')){
        $s=$script:page.DrawOval(0,0,1,1)
    }elseif($type -eq 'decision'){
        [double[]]$pts=@(0,0.5,0.5,1,1,0.5,0.5,0,0,0.5)
        $s=$script:page.DrawPolyline([ref]$pts,0)
    }elseif($type -eq 'data'){
        [double[]]$pts=@(0,0,0.2,1,1,1,0.8,0,0,0)
        $s=$script:page.DrawPolyline([ref]$pts,0)
    }else{$s=$script:page.DrawRectangle(0,0,1,1)}
    if($type -in @('current_source','voltage_source')){
        $selection=$script:page.CreateSelection(0,0,0);$selection.Select($s,2)
        if($type -eq 'current_source'){
            $a=$script:page.DrawLine(0.5,0.75,0.5,0.25);$a.CellsU('EndArrow').FormulaU='4';$selection.Select($a,2)
        }else{
            foreach($p in @(@(0.35,0.7,0.65,0.7),@(0.5,0.55,0.5,0.85),@(0.35,0.3,0.65,0.3))){
                $a=$script:page.DrawLine($p[0],$p[1],$p[2],$p[3]);$selection.Select($a,2)
            }
        }
        $s=$selection.Group()
        # Newly grouped primitives do not automatically get proportional child formulas.
        # Bind each child's local geometry to the group dimensions before any resizing.
        $gw=$s.CellsU('Width').ResultIU;$gh=$s.CellsU('Height').ResultIU
        foreach($child in $s.Shapes){
            if($child.OneD){
                foreach($name in @('BeginX','EndX')){$v=$child.CellsU($name).ResultIU/$gw;$child.CellsU($name).FormulaU='Sheet.'+$s.ID+'!Width*'+(F $v)}
                foreach($name in @('BeginY','EndY')){$v=$child.CellsU($name).ResultIU/$gh;$child.CellsU($name).FormulaU='Sheet.'+$s.ID+'!Height*'+(F $v)}
            }else{
                foreach($name in @('PinX','Width')){$v=$child.CellsU($name).ResultIU/$gw;$child.CellsU($name).FormulaU='Sheet.'+$s.ID+'!Width*'+(F $v)}
                foreach($name in @('PinY','Height')){$v=$child.CellsU($name).ResultIU/$gh;$child.CellsU($name).FormulaU='Sheet.'+$s.ID+'!Height*'+(F $v)}
            }
        }
    }
    if($type -in @('data','decision')){
        # Place freeform geometry inside a 2D group so off-center ports use a stable
        # group coordinate transform during reflection, just like circuit masters.
        $selection=$script:page.CreateSelection(0,0,0);$selection.Select($s,2);$s=$selection.Group()
        $gw=$s.CellsU('Width').ResultIU;$gh=$s.CellsU('Height').ResultIU
        foreach($child in $s.Shapes){
            foreach($name in @('PinX','Width')){$v=$child.CellsU($name).ResultIU/$gw;$child.CellsU($name).FormulaU='Sheet.'+$s.ID+'!Width*'+(F $v)}
            foreach($name in @('PinY','Height')){$v=$child.CellsU($name).ResultIU/$gh;$child.CellsU($name).FormulaU='Sheet.'+$s.ID+'!Height*'+(F $v)}
        }
    }
    foreach($pinDef in $def.pins.PSObject.Properties){
        $row=$s.AddNamedRow(7,$pinDef.Name,0)
        $s.CellsSRC(7,$row,0).FormulaU='Width*'+(F $pinDef.Value.u)
        $s.CellsSRC(7,$row,1).FormulaU='Height*'+(F $pinDef.Value.v)
    }
    Set-Fill $s ([string](Prop $item 'fill' '#ffffff'))
    return $s
}
function Apply-Text($s,$item,[bool]$center=$false){
    $s.Text=[string](Prop $item 'text' '')
    $s.CellsU('Char.Font').FormulaU=[string]$script:fontId
    $s.CellsU('Char.Size').FormulaU=(F ([double](Prop $item 'font_size' (Prop $item 'size' 13))))+' pt'
    $s.CellsU('Char.Color').FormulaU=Color ([string](Prop $item 'text_color' (Prop $item 'color' '#111111')))
    $s.CellsU('Char.Style').FormulaU=[string][int](Prop $item 'style' 0)
    $s.CellsU('Para.HorzAlign').FormulaU=$(if($center){'1'}else{'0'});$s.CellsU('VerticalAlign').FormulaU='1'
    foreach($margin in @('LeftMargin','RightMargin','TopMargin','BottomMargin')){$s.CellsU($margin).FormulaU='0 pt'}
    $offset=0
    foreach($run in (Prop $item 'runs' @())){
        $end=$offset+([string]$run.text).Length
        if($end -gt $offset){
            $ch=$s.Characters;$ch.Begin=$offset;$ch.End=$end
            if(Prop $run 'sub' $false){$ch.CharProps(4)=2}
            if(Prop $run 'sup' $false){$ch.CharProps(4)=1}
            if($null -ne (Prop $run 'style' $null)){$ch.CharProps(2)=[int]$run.style}
        }
        $offset=$end
    }
    foreach($metric in @('MeasuredTextWidth','MeasuredTextHeight')){if(-not $s.CellExistsU('User.'+$metric,0)){$null=$s.AddNamedRow(242,$metric,0)}}
    $s.CellsU('User.MeasuredTextWidth').FormulaU='TEXTWIDTH(TheText)'
    $s.CellsU('User.MeasuredTextHeight').FormulaU='TEXTHEIGHT(TheText,Width)'
}
function Place($item){
    $id=[string]$item.id
    Write-Verbose ('Place '+$id)
    if($script:objects.ContainsKey($id) -or $id.Contains('.')){throw "Invalid/duplicate component ID $id"}
    $def=$catalog.components.PSObject.Properties[[string]$item.type]
    if($null -eq $def){throw "Unknown component type $($item.type)"}
    $def=$def.Value
    if($null -ne $spec.extra_types.PSObject.Properties[[string]$item.type]){$s=Custom-Shape $item $def}
    else{$s=$script:page.Drop($script:stencil.Masters.ItemU($def.master),0,0)}
    $s.NameU=$id;$s.Data1=[string]$item.type;$s.Data2=$id
    $s.CellsU('Width').ResultIU=(PX ([double](Prop $item 'w' ($def.width/$scale))))
    $s.CellsU('Height').ResultIU=(PX ([double](Prop $item 'h' ($def.height/$scale))))
    $s.CellsU('Angle').FormulaU=(F ([double](Prop $item 'rotate' 0)))+' deg'
    if(Prop $item 'flip_x' $false){$s.CellsU('FlipX').FormulaU='1'}
    if(Prop $item 'flip_y' $false){$s.CellsU('FlipY').FormulaU='1'}
    $s.CellsU('PinX').ResultIU=PX $item.at[0];$s.CellsU('PinY').ResultIU=PY $item.at[1]
    $script:objects[$id]=@{shape=$s;definition=$def;item=$item}
    if(Prop $item 'anchor' ''){
        $p=Pin ($id+'.'+$item.anchor)
        $s.CellsU('PinX').ResultIU+=(PX $item.at[0])-$p.x
        $s.CellsU('PinY').ResultIU+=(PY $item.at[1])-$p.y
    }
    # Align to real existing pins, not rounded guesses of transistor geometry.
    $align=Prop $item 'align' $null
    if($align){
        $own=Pin ($id+'.'+$item.anchor)
        if(Prop $align 'x' ''){$target=Pin $align.x;$s.CellsU('PinX').ResultIU+=$target.x-$own.x}
        if(Prop $align 'y' ''){$target=Pin $align.y;$s.CellsU('PinY').ResultIU+=$target.y-$own.y}
    }
    $color=[string](Prop $item 'color' '#111111')
    Paint $s $color ([double](Prop $item 'weight' 1.6))
    if($item.type -eq 'junction'){
        $s.CellsU('FillForegnd').FormulaU=Color $color
        if(Prop $item 'hidden' $false){$s.CellsU('LinePattern').FormulaU='0';$s.CellsU('FillPattern').FormulaU='0'}
    }
    if(Prop $item 'text' ''){Apply-Text $s $item $true}
    if($item.type -eq 'container'){$s.SendToBack()}
    $script:componentRecords+=@{id=$id;type=$item.type;shape_id=$s.ID;width=$s.CellsU('Width').ResultIU;height=$s.CellsU('Height').ResultIU}
    return $s
}
function Anchor([double]$x,[double]$y){
    $script:anchorCount++
    $id='route_'+$script:anchorCount
    $s=Place ([pscustomobject]@{id=$id;type='junction';at=@($x,$y);w=0.02;h=0.02;hidden=$true})
    return $id+'.P'
}
function Segment([string]$a,[string]$b,[string]$color,[double]$weight,[string]$net,[string]$edgeId,[string]$kind,[bool]$beginArrow,[bool]$endArrow){
    Write-Verbose ('Wire '+$a+' -> '+$b)
    $p=Pin $a;$q=Pin $b
    if([math]::Abs($p.x-$q.x) -gt 0.0001 -and [math]::Abs($p.y-$q.y) -gt 0.0001){throw "Non-orthogonal route: $a -> $b"}
    # Keep coincident pin-to-junction connections as zero-length glued wires.
    # A tiny construction offset avoids a degenerate DrawLine call; GlueTo collapses it.
    $s=$script:page.DrawLine($p.x,$p.y,($q.x+0.0000001),$q.y)
    $s.CellsU('BeginX').GlueTo($p.cell);$s.CellsU('EndX').GlueTo($q.cell)
    $s.CellsU('LineColor').FormulaU=Color $color;$s.CellsU('LineWeight').FormulaU=(F $weight)+' pt'
    $s.CellsU('BeginArrow').FormulaU=$(if($beginArrow){'4'}else{'0'});$s.CellsU('EndArrow').FormulaU=$(if($endArrow){'4'}else{'0'});$s.Data1='wire';$s.Data2=$net
    $script:wireRecords+=@{shape=$s;id=$s.ID;from=$a;to=$b;net=$net;edge_id=$edgeId;kind=$kind}
}
function Add-Label($label){
    $x=[double]$label.at[0];$y=[double]$label.at[1]
    $w=[double](Prop $label 'w' 60);$h=[double](Prop $label 'h' 26)
    $s=$script:page.DrawRectangle((PX $x),(PY ($y+$h)),(PX ($x+$w)),(PY $y))
    $s.NameU='label_'+$s.ID;$s.Data1='annotation';$s.Text=[string]$label.text
    $s.CellsU('LinePattern').FormulaU='0';$s.CellsU('FillPattern').FormulaU='0'
    Apply-Text $s $label ([bool](Prop $label 'center' $false))
    $script:labelRecords+=@{shape=$s;item=$label}
}
function Route-Wire($wire){
    $path=@([string]$wire.from)
    foreach($bend in (Prop $wire 'via' @())){$path+=Anchor $bend[0] $bend[1]}
    $path+=[string]$wire.to
    $expanded=@($path[0])
    for($i=1;$i -lt $path.Count;$i++){
        $a=Pin $expanded[-1];$b=Pin $path[$i]
        if([math]::Abs($a.x-$b.x) -gt 0.0001 -and [math]::Abs($a.y-$b.y) -gt 0.0001){
            $route=[string](Prop $wire 'route' 'hv')
            if($route -eq 'strict'){throw "Non-orthogonal explicit route $($wire.id)"}
            if($route -eq 'vh'){$expanded+=Anchor ($a.x/$scale) (($pageHeight-$b.y)/$scale)}
            elseif($route -eq 'hv'){$expanded+=Anchor ($b.x/$scale) (($pageHeight-$a.y)/$scale)}
            else{throw "Unknown route $route"}
        }
        $expanded+=$path[$i]
    }
    $kind=[string](Prop $wire 'kind' 'wire');$arrow=[string](Prop $wire 'arrow' 'end')
    for($i=0;$i -lt $expanded.Count-1;$i++){
        Segment $expanded[$i] $expanded[$i+1] ([string](Prop $wire 'color' '#111111')) ([double](Prop $wire 'weight' 1.4)) ([string](Prop $wire 'net' '')) $wire.id $kind ($kind -eq 'edge' -and $arrow -eq 'both' -and $i -eq 0) ($kind -eq 'edge' -and $arrow -ne 'none' -and $i -eq $expanded.Count-2)
    }
    if(Prop $wire 'label' ''){
        $a=Pin $wire.from;$b=Pin $wire.to
        Add-Label ([pscustomobject]@{text=$wire.label;at=@(((($a.x+$b.x)/2/$scale)+5),((($pageHeight-($a.y+$b.y)/2)/$scale)-22));w=70;h=22;font_size=12})
    }
}
function Layout-Check(){
    $bounds=@{}
    foreach($entry in $script:objects.GetEnumerator()){
        $item=$entry.Value.item;if($item.type -eq 'junction'){continue}
        $s=$entry.Value.shape;$l=0.;$b=0.;$r=0.;$t=0.;$s.BoundingBox(1,[ref]$l,[ref]$b,[ref]$r,[ref]$t)
        $bounds[$entry.Key]=@($l,$b,$r,$t)
        if($l -lt -0.01 -or $b -lt -0.01 -or $r -gt (PX $spec.canvas[0])+0.01 -or $t -gt $pageHeight+0.01){$script:layoutFindings+=@{id='bounds-'+$entry.Key;message='Object outside page';object=$entry.Key}}
        if(Prop $item 'text' ''){
            $need=$s.CellsU('User.MeasuredTextHeight').ResultIU
            if($need -gt $s.CellsU('Height').ResultIU+0.01){$script:layoutFindings+=@{id='text-'+$entry.Key;message='Text may overflow';object=$entry.Key}}
        }
    }
    foreach($item in $spec.components){
        if((Prop $item 'parent' '') -and $bounds.ContainsKey($item.id)){
            $a=$bounds[$item.id];$p=$bounds[$item.parent]
            if($a[0] -lt $p[0] -or $a[1] -lt $p[1] -or $a[2] -gt $p[2] -or $a[3] -gt $p[3]){$script:layoutFindings+=@{id='parent-'+$item.id;message='Child outside container';object=$item.id}}
        }
    }
    $textBounds=@()
    foreach($label in $script:labelRecords){
        $s=$label.shape;$item=$label.item
        $th=$s.CellsU('User.MeasuredTextHeight').ResultIU;$tw=[math]::Min($s.CellsU('User.MeasuredTextWidth').ResultIU,$s.CellsU('Width').ResultIU)
        if($th -gt $s.CellsU('Height').ResultIU+0.01){$script:layoutFindings+=@{id='label-'+$s.ID;message='Label may overflow';text=$item.text}}
        $tx=$s.CellsU('PinX').ResultIU-$s.CellsU('Width').ResultIU/2
        if(Prop $item 'center' $false){$tx=$s.CellsU('PinX').ResultIU-$tw/2}
        $ty=$s.CellsU('PinY').ResultIU
        $bb=@($tx,($ty-$th/2),($tx+$tw),($ty+$th/2))
        foreach($previous in $textBounds){
            $p=$previous.bounds
            if([math]::Min($bb[2],$p[2])-[math]::Max($bb[0],$p[0]) -gt 0.025 -and [math]::Min($bb[3],$p[3])-[math]::Max($bb[1],$p[1]) -gt 0.025){$script:layoutFindings+=@{id=('label-overlap-'+$s.ID+'-'+$previous.id);message='Text bounds overlap';texts=@($item.text,$previous.text)}}
        }
        foreach($id in $bounds.Keys){
            if($script:objects[$id].item.type -eq 'container'){continue}
            $p=$bounds[$id]
            if([math]::Min($bb[2],$p[2])-[math]::Max($bb[0],$p[0]) -gt 0.025 -and [math]::Min($bb[3],$p[3])-[math]::Max($bb[1],$p[1]) -gt 0.025){$script:layoutFindings+=@{id=('label-symbol-'+$s.ID+'-'+$id);message='Text overlaps symbol bounds (including fixed leads)';text=$item.text;object=$id}}
        }
        $textBounds+=@{id=$s.ID;text=$item.text;bounds=$bb}
    }
    foreach($w in $script:wireRecords){
        $s=$w.shape;$x1=$s.CellsU('BeginX').ResultIU;$x2=$s.CellsU('EndX').ResultIU;$y1=$s.CellsU('BeginY').ResultIU;$y2=$s.CellsU('EndY').ResultIU
        foreach($id in $bounds.Keys){
            $item=$script:objects[$id].item
            if($item.type -eq 'container' -or $w.from.Split('.')[0] -eq $id -or $w.to.Split('.')[0] -eq $id){continue}
            $bb=$bounds[$id];$margin=0.025
            if(([math]::Min($x1,$x2) -lt $bb[2]-$margin) -and ([math]::Max($x1,$x2) -gt $bb[0]+$margin) -and ([math]::Min($y1,$y2) -lt $bb[3]-$margin) -and ([math]::Max($y1,$y2) -gt $bb[1]+$margin)){
                $script:layoutFindings+=@{id=('route-'+$w.id+'-'+$id);message='Route crosses unrelated symbol bounds';edge=$w.edge_id;object=$id}
            }
        }
    }
}
function Check-Connections([bool]$orthogonal){
    $maxError=0.0;$glues=0
    foreach($r in $script:wireRecords){
        $s=$r.shape
        # Visio can lazily recalculate PAR(PNT(...)) after a reflected shape moves.
        # Read both ends once to settle dependent cells before measuring; do not re-glue.
        foreach($coordinate in @('BeginX','BeginY','EndX','EndY')){$null=$s.CellsU($coordinate).ResultIU}
        foreach($end in @(@('Begin',$r.from),@('End',$r.to))){
            $p=Pin $end[1]
            $dx=$s.CellsU($end[0]+'X').ResultIU-$p.x;$dy=$s.CellsU($end[0]+'Y').ResultIU-$p.y
            $err=[math]::Sqrt($dx*$dx+$dy*$dy);$maxError=[math]::Max($maxError,$err)
            if($err -gt 0.00001){throw "Disconnected wire $($r.id) $($end[0]) to $($end[1]): $err inches; actual=$($s.CellsU($end[0]+'X').ResultIU),$($s.CellsU($end[0]+'Y').ResultIU) expected=$($p.x),$($p.y); formula=$($s.CellsU($end[0]+'X').FormulaU)"}
            $matches=@($s.Connects | Where-Object {$_.FromCell.Name -eq ($end[0]+'X') -and $_.ToSheet.ID -eq $p.shape.ID -and $_.ToCell.Name -eq $p.cell.Name})
            if($matches.Count -ne 1){
                Write-Host ('Expected '+$end[0]+'X -> '+$p.shape.ID+'/'+$p.cell.Name)
                foreach($cc in $s.Connects){Write-Host ($cc.FromCell.Name+' -> '+$cc.ToSheet.ID+'/'+$cc.ToCell.Name)}
                throw "Missing/wrong GlueTo target for $($r.id) $($end[0])"
            }
            $glues++
        }
        if($orthogonal){
            $dx=[math]::Abs($s.CellsU('BeginX').ResultIU-$s.CellsU('EndX').ResultIU)
            $dy=[math]::Abs($s.CellsU('BeginY').ResultIU-$s.CellsU('EndY').ResultIU)
            if($dx -gt 0.0001 -and $dy -gt 0.0001){throw "Wire $($r.id) no longer orthogonal"}
        }
    }
    return @{wire_segments=$script:wireRecords.Count;verified_glued_endpoints=$glues;max_endpoint_error_inches=$maxError}
}
$app=$null;$doc=$null;$script:stencil=$null
try{
    Write-Verbose 'Start Visio'
    $app=New-Object -ComObject Visio.InvisibleApp
    $app.AlertResponse=7
    Write-Verbose 'Open library'
    $script:stencil=$app.Documents.OpenEx((Join-Path $assetDir $catalog.stencil),194)
    Write-Verbose 'New document'
    $doc=$app.Documents.Add('');$script:page=$doc.Pages.Item(1)
    Write-Verbose 'Page setup'
    $script:page.Name='Drawing'
    $script:page.PageSheet.CellsU('PageWidth').ResultIU=PX $spec.canvas[0]
    $script:page.PageSheet.CellsU('PageHeight').ResultIU=$pageHeight
    Write-Verbose 'Font setup'
    $script:fontId=$doc.Fonts.Item([string](Prop $spec 'font' 'Arial')).ID
    # Page.Export crops to drawing extents; an editable white page rectangle fixes the
    # coordinate frame for all regional comparison crops and prevents margin clipping.
    $paper=$script:page.DrawRectangle(0,0,(PX $spec.canvas[0]),$pageHeight)
    $paper.NameU='page_background';$paper.Data1='annotation-frame'
    $paper.CellsU('LinePattern').FormulaU='0';$paper.CellsU('FillPattern').FormulaU='1';$paper.CellsU('FillForegnd').FormulaU='RGB(255,255,255)'
    Write-Verbose 'Render components'
    foreach($item in $spec.components){Place $item | Out-Null}
    foreach($node in $spec.nodes){
        Place ([pscustomobject]@{id=$node.id;type='junction';at=$node.at;w=(Prop $node 'diameter' 5.5);h=(Prop $node 'diameter' 5.5);hidden=(Prop $node 'hidden' $false);color=(Prop $node 'color' '#111111')}) | Out-Null
    }
    foreach($wire in $spec.wires){Route-Wire $wire}
    foreach($label in $spec.labels){Add-Label $label}
    foreach($ann in $spec.annotations){
        if($ann.kind -eq 'frame'){
            $s=$script:page.DrawRectangle((PX $ann.at[0]),(PY ($ann.at[1]+$ann.h)),(PX ($ann.at[0]+$ann.w)),(PY $ann.at[1]))
            if(Prop $ann 'rounding' 0){$s.CellsU('Rounding').ResultIU=PX $ann.rounding}
            $s.Data1='annotation-frame';$s.CellsU('LineColor').FormulaU=Color ([string](Prop $ann 'color' '#555555'))
            $s.CellsU('FillPattern').FormulaU='0'
            if(Prop $ann 'fill' ''){$s.CellsU('FillPattern').FormulaU='1';$s.CellsU('FillForegnd').FormulaU=Color $ann.fill}
            $s.SendToBack()
        }else{
            for($i=0;$i -lt $ann.points.Count-1;$i++){
                $a=$ann.points[$i];$b=$ann.points[$i+1];$s=$script:page.DrawLine((PX $a[0]),(PY $a[1]),(PX $b[0]),(PY $b[1]))
                $s.Data1='annotation-arrow';$s.CellsU('LineColor').FormulaU=Color ([string](Prop $ann 'color' '#111111'));$s.CellsU('LineWeight').FormulaU='1.4 pt'
                $s.CellsU('BeginArrow').FormulaU='0';$s.CellsU('EndArrow').FormulaU=$(if($ann.kind -eq 'arrow' -and $i -eq $ann.points.Count-2){'4'}else{'0'})
            }
        }
    }
    foreach($arrow in (Prop $spec 'arrows' @())){
        $pts=$arrow.points
        if(Prop $arrow 'bezier' $false){
            if(($pts.Count-1)%3 -ne 0){throw 'Cubic Bezier arrows require 3k+1 control points'}
            [double[]]$xy=@(foreach($pt in $pts){PX $pt[0];PY $pt[1]})
            $s=$script:page.DrawBezier([ref]$xy,3,8)
            $s.Data1='annotation';$s.CellsU('FillPattern').FormulaU='0'
            $s.CellsU('LineColor').FormulaU=Color ([string](Prop $arrow 'color' '#c00000'))
            $s.CellsU('LineWeight').FormulaU='1.6 pt';$s.CellsU('EndArrow').FormulaU='4'
            continue
        }
        for($i=0;$i -lt ($pts.Count-1);$i++){
            $s=$script:page.DrawLine((PX $pts[$i][0]),(PY $pts[$i][1]),(PX $pts[$i+1][0]),(PY $pts[$i+1][1]))
            $s.Data1='annotation';$s.CellsU('LineColor').FormulaU=Color ([string](Prop $arrow 'color' '#c00000'));$s.CellsU('LineWeight').FormulaU='1.6 pt'
            if($i -eq $pts.Count-2){$s.CellsU('EndArrow').FormulaU='4'}
        }
    }
    $report=Check-Connections $true
    $report.transform_tests=@()
    if($TestTransforms){
        foreach($testId in (Prop $spec 'transform_test_ids' @())){
            Write-Verbose ('Transform tests for '+$testId)
            $s=$script:objects[$testId].shape;$oldX=$s.CellsU('PinX').ResultIU;$oldAngle=$s.CellsU('Angle').FormulaU;$oldFlip=$s.CellsU('FlipX').FormulaU
            $s.CellsU('PinX').ResultIU=$oldX+0.37
            Write-Verbose 'Check translation'
            $move=Check-Connections $false
            $s.CellsU('Angle').FormulaU='90 deg'
            Write-Verbose 'Check rotation'
            $rotate=Check-Connections $false
            $s.CellsU('FlipX').FormulaU='1'
            Write-Verbose 'Check reflection'
            $mirror=Check-Connections $false
            $s.CellsU('FlipX').FormulaU=$oldFlip;$s.CellsU('Angle').FormulaU=$oldAngle;$s.CellsU('PinX').ResultIU=$oldX
            $restored=Check-Connections $true
            $report.transform_tests+=@{component=$testId;translate='passed';rotate_90='passed';mirror='passed';restored='passed'}
        }
    }
    Layout-Check
    $paper.SendToBack()
    $doc.SaveAs($Output) | Out-Null
    $script:page.Export($stem+'.svg');$script:page.Export($stem+'.png')
    $doc.ExportAsFixedFormat(1,$stem+'.pdf',1,0)
    foreach($ext in @('.vsdx','.svg','.png','.pdf')){if((Get-Item -LiteralPath ($stem+$ext)).Length -eq 0){throw "Empty export $ext"}}
    $report.components=$script:componentRecords
    $report.wires=@($script:wireRecords | ForEach-Object {@{id=$_.id;from=$_.from;to=$_.to;net=$_.net;edge_id=$_.edge_id;kind=$_.kind}})
    $report.layout_findings=$script:layoutFindings
    $report.compiled_sha256=(Get-FileHash -LiteralPath $Model -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.model=[IO.Path]::GetFileName($Model);$report.source_of_truth=[IO.Path]::GetFileName($Output)
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath ($stem+'.qa.json') -Encoding UTF8
    Write-Output ($report | Select-Object wire_segments,verified_glued_endpoints,max_endpoint_error_inches,transform_tests | ConvertTo-Json -Depth 5 -Compress)
    Write-Output ('Saved: '+$Output)
}finally{
    if($doc){$doc.Saved=$true;$doc.Close()}
    if($script:stencil){$script:stencil.Close()}
    if($app){$app.Quit()}
}

