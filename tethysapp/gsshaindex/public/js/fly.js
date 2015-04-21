function dynamicReload(){
	setTimeout(function(){
		dynamicReload();
	}, 5000);
};

$('.run-btn').click(function(){
    id = $(this).attr('data-id')
    $(this).css('visibility','hidden');
    $('tr#' + id + ' .status').html('processing');
});