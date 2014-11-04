// Make synchronous calls
jQuery.ajaxSetup({async:false});

// Array to keep track of monitors added to screen
var monitors = [];

// Function to extract URL parameters
function getURLParameter(name) {
    return decodeURIComponent((new RegExp('[?|&]' + name + '=' + '([^&;]+?)(&|#|;|$)').exec(location.search)||[,""])[1].replace(/\+/g, '%20'))||null
}

// Get URL parameter specifying how many points to get (default to 60)
var limit = getURLParameter('limit')
if(limit === null){
    limit = 60
};

// Get URL parameter access_token
var access_token = getURLParameter('access_token')
if(access_token === null){
    access_token = ""
};

// Get URL parameter with number of columns in our plot grid
var columns = getURLParameter('columns')
if(columns === null){
    columns = 3
};

// Get URL parameter with number of points to show when detailing chart
var limitDetailed = getURLParameter('limit_detailed')
if(limitDetailed === null){
    limitDetailed = 1440
};

// Callbacks to map JSON to arrays recognizable by dygraphs
function Json2PredictionArray(d) {
    return [new Date(d.time*1000), d.actual, d.predicted];
}

function Json2AnomalyArray(d) {
    return [new Date(d.time*1000), d.anomaly, d.likelihood];
}

// Function using dygraphs to draw a interactive detailed plot
function drawDetailed(id){
  // Get monitor to be draw
  var monitor = monitors[id];

  // Get data for monitor
  $(document).ready(function(){
      $.getJSON( "/results/" + monitor.check_id + "?limit=" + limitDetailed + "&access_token=" + access_token, function( dataset ) {
          data = dataset.results
      });
  });
  // Arrays to be passed to dygraphs
  var pred = data.map(Json2PredictionArray);
  var anomalies = data.map(Json2AnomalyArray);

  // Code to plot predictions and scores synced
  var blockRedraw = false;
  var initialized = false;

  // Create HTML elements
  var div_pred = "<div class='chart-predictions' id='chart-overlay-predictions'></div>"
  var div_panel = "<div class='chart-panel' id='chart-overlay-panel'></div>"
  var div_anomaly = "<div class='chart-anomalies' id='chart-overlay-anomalies'></div>"
  $('.overlay-bg').empty();
  $('.overlay-bg').append(div_pred, div_panel, div_anomaly)
  $('.overlay-bg').show(); // Show overlay

  // Plot predictions
  var g1_pred = new Dygraph(
    document.getElementById("chart-overlay-predictions"),
    pred, {
      title: monitor.check_name,
      showRangeSelector: true,
      ylabel: monitor.value_label + " (" + monitor.value_unit + ")",
      legend: 'always',
      labelsDivStyles: { 'textAlign': 'right', 'background': 'rgba(180,180,180,0.65)'},
      labels: ['Time', 'Actual', 'Predicted'],
      axisLabelFontSize: 12,
      drawCallback: function(me, initial) {
        if (blockRedraw || initial) return;
        blockRedraw = true;
        var range = me.xAxisRange();
        var yrange = me.yAxisRange();
        for (var j = 0; j < 2; j++) {
          if (gs[j] == me) continue;
          gs[j].updateOptions( {
            dateWindow: range,
            yvalueRange: [0, 1]
          } );
        }
        blockRedraw = false;
      },
      highlightCallback: function(e,x,pts,row,seriesName) {
       gs[1].setSelection(row);
     }
    }
  );

  var g1_anomaly = new Dygraph(
    document.getElementById("chart-overlay-anomalies"),
    anomalies, {
      ylabel: 'Score',
      legend: 'always',
      fillGraph: true,
      labelsDivStyles: { 'textAlign': 'right', 'background': 'rgba(200,200,200,0.65)'},
      labels: ['Time', 'Anomaly', 'Likelihood'],
      colors: ['rgb(6,60,210)', 'rgb(80,20,120)'],
      axisLabelFontSize: 12,
      valueRange: [0, 1.2],
      interactionModel: {
        mousedown: function(event, g, context) {
          context.initializeMouseDown(event, g, context);
          Dygraph.startPan(event, g, context);
        },
        mousemove: function(event, g, context) {
          if (context.isPanning) {
            Dygraph.movePan(event, g, context);
            g1_anomaly.updateOptions({valueRange:[0, 1.2]});
          }
        },
        mouseup: function(event, g, context) {
          if (context.isPanning) {
            Dygraph.endPan(event, g, context);
          }
        }
      },
      drawCallback: function(me, initial) {
        if (blockRedraw || initial) return;
        blockRedraw = true;
        var range = me.xAxisRange();
        var yrange = me.yAxisRange();
        for (var j = 0; j < 2; j++) {
          if (gs[j] == me) continue;
          gs[j].updateOptions( {
            dateWindow: range
          } );
        }
        blockRedraw = false;
      },
      highlightCallback: function(e,x,pts,row,seriesName) {
       gs[0].setSelection(row);
     }
    }
  )

  gs = [g1_pred, g1_anomaly];
}

// Function using dygraphs to draw a interactive detailed plot
function drawSimple(id, width){
  // Get monitor to be draw
  var monitor = monitors[id];

  // Get data for monitor
  $(document).ready(function(){
      $.getJSON( "/results/" + monitor.check_id + "?limit=60&access_token=" + access_token, function( dataset ) {
          data = dataset.results
      });
  });
  // Arrays to be passed to dygraphs
  var pred = data.map(Json2PredictionArray);
  var anomalies = data.map(Json2AnomalyArray);

  // Code to plot predictions and scores synced
  var blockRedraw = false;
  var initialized = false;

  // Create HTML elements
  var div_pred = "<div class='chart-predictions' id='chart-predictions-" + id + "'></div>"
  var div_panel = "<div class='chart-panel' id='chart-panel-" + id + "'></div>"
  var div_anomaly = "<div class='chart-anomalies' id='chart-anomalies-" + id + "'></div>"
  $('#cell-' + id).empty();
  $('#cell-' + id).append(div_pred, div_panel, div_anomaly)

  // Plot predictions
  var gs = [] // Array with plots for this id
  var g1_pred = new Dygraph(
    document.getElementById("chart-predictions-" + id),
    pred, {
      title: monitor.check_name,
      ylabel: monitor.value_label + " (" + monitor.value_unit + ")",
      labelsDivStyles: { 'textAlign': 'right', 'background': 'rgba(180,180,180,0.65)'},
      labels: ['Time', 'Actual', 'Predicted'],
      axisLabelFontSize: 12,
      highlightCallback: function(e,x,pts,row,seriesName) {
        gs[1].setSelection(row); // Synchronize both charts
      },
      unhighlightCallback: function(e,x,pts,row,seriesName) {
        gs[1].clearSelection(); // Synchronize both charts
      }
    }
  );

  var g1_anomaly = new Dygraph(
    document.getElementById("chart-anomalies-" + id),
    anomalies, {
      ylabel: 'Score',
      fillGraph: true,
      labelsDivStyles: { 'textAlign': 'right', 'background': 'rgba(200,200,200,0.65)'},
      labels: ['Time', 'Anomaly', 'Likelihood'],
      colors: ['rgb(6,60,210)', 'rgb(80,20,120)'],
      axisLabelFontSize: 12,
      valueRange: [0, 1.2],
      interactionModel: {
        mousedown: function(event, g, context) {
          context.initializeMouseDown(event, g, context);
          Dygraph.startPan(event, g, context);
        },
        mousemove: function(event, g, context) {
          if (context.isPanning) {
            Dygraph.movePan(event, g, context);
            g1_anomaly.updateOptions({valueRange:[0, 1.2]});
          }
        },
        mouseup: function(event, g, context) {
          if (context.isPanning) {
            Dygraph.endPan(event, g, context);
          }
        }
      },
      highlightCallback: function(e,x,pts,row,seriesName) {
        gs[0].setSelection(row); // Synchronize both charts
      },
      unhighlightCallback: function(e,x,pts,row,seriesName) {
        gs[0].clearSelection(); // Synchronize both charts
      }
    }
  )

  gs = [g1_pred, g1_anomaly];

  // Dynamically update plot
  window.intervalId = setInterval(function() {
    // Get data for monitor
    $(document).ready(function(){
      $.getJSON( "/results/" + monitor.check_id + "?limit=60&access_token=" + access_token, function( dataset ) {
            data = dataset.results
      });
    });

    pred = data.map(Json2PredictionArray);
    anomalies = data.map(Json2AnomalyArray);

    blockRedraw = true;
    g1_pred.updateOptions( { 'file': pred } );
    g1_anomaly.updateOptions( { 'file': anomalies } );
    }, 5000);

}

// Create a table with cells in which we'll draw our charts
function createGraphTable(){
    var columns = window.columns;
    var rows = 0;
    var id = 0;
    $(document).ready(function(){
        $.getJSON( "/monitors?access_token=" + access_token, function( data ) {
            rows = parseInt(data.monitors.length/columns) + 1;
            for (r = 0; r < rows; r++) {
              $("#table").append("<tr id=\"tr" + r + "\"></tr>");
                for (c = 0; c < columns; c++) {
                    id = r*columns + c;
                    if(id < data.monitors.length){
                      $("#tr" + r).append("<td onclick=\"drawDetailed(" + id + ")\" id=\"td" + id + "\"><div style='position: relative;' class=\"cell-chart\" id=\"cell-" + id + "\"></div></td>");
                    }
                }
            };
            // Populate monitors array
            jQuery.each(data.monitors.reverse(), function(index, value) {
                monitors.push({'check_id': value.id, 'check_name': value.name, 'value_label': value.value_label, 'value_unit': value.value_unit});
            });
        });
    });
}

// Create charts on the cells
function createPlots(width){
    var columns = window.columns;
    var w = (width-80)/columns;

    $(document).ready(function(){
      $(".cell-chart").css("width", w +"px");
      for (i = 0; i < monitors.length; i++) {
      drawSimple(i);
    }
    });
}

// Implement a simple delay to be used on resize below
var delay = (function(){
    var timer = 0;
    return function(callback, ms){
        clearTimeout (timer);
        timer = setTimeout(callback, ms);
    };
})();

$(window).resize(function() {
    delay(function(){
        var win = $(this);
        $('.overlay-bg').hide(); // Hide overlay
        createPlots($(this).width());
    }, 500);
});

// Hide overlay when click outside
$(document).mouseup(function (e)
{
    var container = $(".overlay-bg");

    if (!container.is(e.target) // if the target of the click isn't the container...
        && container.has(e.target).length === 0) // ... nor a descendant of the container
    {
        container.hide();
    }
});
