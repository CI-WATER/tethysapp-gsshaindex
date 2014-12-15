function submitRunRequest(id, status_element) {
	$(status_element).html('processing');

	$.ajax({
					method: "post",
					url: id.toString() + "/fly"
	});

	updateUI();
}


$(function(){
	done = true;
	$('td.status').each(function(){
		if ($(this).attr('data-status') === 'pending') {
			var id = $(this).attr('data-id');
			submitRunRequest(id, this);
		}
	});

	dynamicReload();
	updateUI();
});

function updateUI(){
	$('#jobs-table-load').load("ajax/load_jobs");
}

function dynamicReload(){
	setTimeout(function(){
		updateUI();
		console.log('update ui');
		dynamicReload();
	}, 5000);
}