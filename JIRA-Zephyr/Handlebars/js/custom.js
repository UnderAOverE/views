var pageCounter = 1;
var projectContainer = document.getElementById("project-info");
var btn = document.getElementById("btn");

btn.addEventListener("click", function() {
  var ourRequest = new XMLHttpRequest();
  ourRequest.open('GET', 'http://localhost/rest/api/2/project');
  ourRequest.onload = function() {
    if (ourRequest.status >= 200 && ourRequest.status < 400) {
      var ourData = JSON.parse(ourRequest.responseText);
      renderHTML(ourData);
    } else {
      console.log("We connected to the server, but it returned an error.");
    }
    
  };

  ourRequest.onerror = function() {
    console.log("Connection error");
  };

  ourRequest.send();
  pageCounter++;
  if (pageCounter > 1) {
    btn.classList.add("hide-me");
  }
});

function renderHTML(data) {
  var htmlString = "";

  for (i = 0; i < data.length; i++) {
    htmlString += "<p>Project " + data[i].name + " has key " + data[i].key + " with ID= " + data[i].id + "";
    htmlString += '.</p>';

  }

  projectContainer.insertAdjacentHTML('beforeend', htmlString);
}