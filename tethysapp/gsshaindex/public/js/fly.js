function dynamicReload(){
	setTimeout(function(){
		dynamicReload();
	}, 5000);
};

$('.run-btn').click(function(){
    console.log('a button was clicked');
    id = $(this).attr('data-id')
    console.log(id)
    $(this).css('visibility','hidden');
    $('tr#' + id + ' .status').html('processing');
});