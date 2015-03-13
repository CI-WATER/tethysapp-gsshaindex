function changeMap(element, shapefile_id, shapefile_description, shapefile_name, shapefile_url, job_id, index_name) {
	$('.shapefile').each(function(file_id){
		$(this).removeClass('active');
	});
	$('#file_id').val(shapefile_id);
	$('#file_name').val(shapefile_name);
	$('#file_url').val(shapefile_url);
	$('.shapefile').each(function(){
		if ($(this).children('a').get(0).id == shapefile_id){
			$(this).addClass('active');
			$('#description').text(shapefile_description);
			$('h1').text("Shapefile: "+$(element).text());
		};
	});
};

window.onload = function(){
	String.prototype.endsWith = function(str)
		{return (this.match(str+"$")==str)};
	watcher = document.getElementById('selected_files');
	var prj_text_area = document.getElementById('projection-text');
	watcher.addEventListener('change', function(e){
		stuff = document.getElementById('selected_files').files || [];
		console.log(stuff);
		for (var i=0; i<stuff.length; i++){
			file_name = stuff[i].name;
			if (file_name.endsWith('.prj') == true){
				var reader = new FileReader();
				prj_file = stuff.item(i);
				reader.onload=function(e){
					console.log(reader.result);
					prj_text_area.value = reader.result;
				};
				reader.readAsText(prj_file);
			};
		};
	});
};

function submit_files(){
	stuff = document.getElementById('selected_files').files || [];
	var prj_text_area = document.getElementById('projection-text');
	console.log(stuff);

	String.prototype.endsWith = function(str)
		{return (this.match(str+"$")==str)};

	prj = false;
	dbf = false;
	shx = false;
	shp = false;
	required_true = true;

	for (var i=0; i<stuff.length; i++){
		file_name = stuff[i].name;
		console.log(file_name);
		if (file_name.endsWith('.shx') == true){
			shx = true;
			shx_file = stuff.item(i);
		};
		if (file_name.endsWith('.shp') == true){
			shp = true;
			shp_file = stuff.item(i);
		};
		if (file_name.endsWith('.dbf') == true){
			dbf = true;
			dbf_file = stuff.item(i);
		};
		if (file_name.endsWith('.prj') == true){
			var reader = new FileReader();
			prj = true;
			prj_file = stuff.item(i);
		};
	};

	if (dbf==false){
		$("#error_message").show();
		required_true = false;
	};
	if (shp==false){
		$("#error_message").show();
		required_true = false;
	};
	if (shx==false){
		$("#error_message").show();
		required_true = false;
	};

	if (required_true == true){
		$("#error_message").hide();
        $("#submit_shapefile_upload").submit();
	};
};

// This uses prj2epsg.org to find the code from the projection file
function send_prj_request(){
	var prj_desc = document.getElementById('projection-text').value;
	console.log("http://prj2epsg.org/search.json?mode=wkt&terms=" + prj_desc);
	$.ajax({
        method:"get",
		url:"/apps/gsshaindex/get-srid-from-wkt",
        data: {url:encodeURIComponent(prj_desc)},
		success: function(data){
			if (data == "error"){
				alert("There was an error with the projection file. Please select a projection.");
				$('#select_projection').modal('toggle');

			}
			else {
				console.log(data);

				$('#projection-number').attr('value', data);

				$('#name_shapefile').modal('toggle');
			};
		},
		error: function(data){
			alert("There was an error with the projection file. Please select a projection.");
			$('#select_projection').modal('toggle');
		}
	});
};

function submit_projection(){
	prj = $('#projections option:selected').val();
	console.log(prj);
	$('#projection-number').attr('value', prj);
	$('#select_projection').modal('toggle');
	$('#name_shapefile').modal('toggle');
};