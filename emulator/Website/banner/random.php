<!DOCTYPE html>
<html>
<head>
       <style>
        html, body {
            margin: 0;
            padding: 0;
            height: 100%;
            overflow: hidden;
        }

        #image-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }

        #image-container img {
            position: absolute;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            object-fit: cover;
            object-position: top left;
        }
    </style>
</head>
<body>
    <div id="image-container">
        <?php
            $files = glob('./img/*.gif');
            $random_file = $files[array_rand($files)];
            echo '<img src="' . $random_file . '" alt="Random Image">';
        ?>
    </div>
</body>
</html>