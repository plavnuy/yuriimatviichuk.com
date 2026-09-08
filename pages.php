<?
include 'tpl/header.php';

switch ($PAGE) {
	case 'neobarocco':
		display_images_header('neobarocco');
		display_text('neobarocco');
		display_images('/pix/neobarocco/');
		break;
	case 'askoldova':
		display_images_header('askoldova');
		display_text('askoldova');
		display_images('/pix/askoldova/');
		display_images('/pix/askoldova/process/');
		break;
	case 'modern':
		display_images_header('modern');
		display_text('modern');
		display_images('/pix/modern1/');
		break;
	case 'renaissance':
		display_images_header('renaissance');
		display_text('renaissance');
		display_images('/pix/renaissance/');
		break;
	case 'functionalism':
		display_images_header('functionalism');
		display_images('/pix/functionalism1/');
		break;
	case 'art':
		display_images_header('art');
		display_text('art');
		display_images('/pix/art/', 'art');
		break;
	case 'valera':
		display_images_header('valera');
		display_images('/pix/valera/', 'valera');
		break;
	case 'ira':
		display_images_header('ira');
		display_images('/pix/ira/', 'ira');
		break;
	case 'contact':
		display_text('contact');
		break;
	case '':
		include 'index.php';
		display_text('index');
		break;
	default:
		display_images_header('404');
		break;
}

include 'tpl/footer.php';
?>