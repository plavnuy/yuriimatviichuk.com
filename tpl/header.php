<?
include 'functions.php';

$LANGS = array('ru', 'uk', 'fr', /*'es',*/ 'nl');

$path = explode('/', $_SERVER['REQUEST_URI']);
if (in_array($path[1], $LANGS)) {
	$LANG = $path[1];
	$PAGE = $path[2];
} else {
	$LANG = reset($LANGS);
	$PAGE = $path[1];
}

$TXT = parse_ini_file("tpl/$LANG/text.ini");

$page_ini_file = "tpl/$LANG/$PAGE.ini";
if(is_file($page_ini_file)) {
	$PAGEINI = parse_ini_file($page_ini_file);
} else {
	$PAGEINI = array(
		'header' => ''
	);
}

?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
	<title><?=$PAGEINI['header']?> <?=$TXT['title']?></title>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
	<meta name="audience" content="all"/>
	<meta name="distribution" content="Global"/>
	<meta name="annotation" content=""/>
	<meta name="description" content=""/>
	<meta name="keywords" content=""/>

	<link href="/img/icon.png" type="image/png" rel="icon" />
	<link rel="stylesheet" href="/inc/main.css" type="text/css" />
</head>
<body>
<? ?>
<div class="superheader">
	<div class='like'>
		<iframe
			src="//www.facebook.com/plugins/like.php?href=http%3A%2F%2Fyuram.com.ua%2F&amp;send=false&amp;layout=button_count&amp;width=450&amp;show_faces=false&amp;action=like&amp;colorscheme=light&amp;font&amp;height=21"
			scrolling="no" frameborder="0" style="border:none; overflow:hidden; width:120px; height:21px;" allowTransparency="true"></iframe>
	</div>
	<div class='lang'>
	<?
		foreach($LANGS as $i) echo "<a href='/$i/'>$i</a> ";
	?>
	</div>
</div>
<div id="ALL">
	<div class="header">
		<a class='logo' href='/<?=$LANG?>/'><img src='/img/logo.png' /></a>
		<div class='menu'>
			<? $uri = $_SERVER['REQUEST_URI']; ?>
			<a href="/<?=$LANG?>/" <? if ($PAGE=='') {?>class="current"<?}?>><?=$TXT['projects']?></a><br/>
			<a href="/<?=$LANG?>/contact" <? if ($PAGE=='contact') {?>class="current"<?}?>><?=$TXT['contacts']?></a>
		</div>
	</div>

	<table class='main'>
	<tr>