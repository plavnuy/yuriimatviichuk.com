<?

function list_images($dir) {
	$handle = opendir($dir);
	$files = array();
	while ($file = readdir($handle)) {
		if (is_file($dir . $file)) $files[] = $file;
	}
	asort($files);
	return $files;
}

function display_images($dir, $ini = false) {
	global $LANG;
	static $c = 0;

	if ($ini) {
		$subs = parse_ini_file("tpl/$LANG/$ini.ini");
	}

	$images = list_images($_SERVER['DOCUMENT_ROOT'] . $dir);
	$total = count($images);
	foreach ($images as $i) {
		$c++
		?>
			<td class='list_image'>
				<a name='image<?=$c?>' href='#image<?=$c+1?>'>
					<img src='<?=$dir?><?=$i?>' alt='' />
				</a>
			</td>
			<td class='list_text'>
				<? if(isset($subs[$i])) echo $subs[$i] ?>
			</td>
		</tr><tr>
		<?
	}
}

function display_text($file) {
	global $LANG;

	?>
		<td class='block_text'>
	<? include ("$LANG/$file.html") ?>
		</td>
		<td class='list_text'>
		</td>
	</tr><tr>
	<?
}

function display_images_header($file) {
	global $LANG;
	global $PAGEINI;

	?><td class='main_image'><h2><?
	if ($file == 404)
		echo "404. Not found";
	else
		echo $PAGEINI['header'];
	?></h2></td><td></td></tr><tr><?
}
?>