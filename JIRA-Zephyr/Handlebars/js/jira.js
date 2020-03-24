var jRequest = new XMLHttpRequest();
jRequest.open('GET', 'https://raw.githubusercontent.com/r2d2c3p0/views/master/JIRA-Zephyr/Handlebars/data/jira_projects.json');
jRequest.onload = function() {
  if (jRequest.status >= 200 && jRequest.status < 400) {
    var data = JSON.parse(jRequest.responseText);
    createProjectTable(data);
  } else {
    console.log("We connected to the server, but it returned an error.");
  }
};

jRequest.onerror = function() {
  console.log("Connection error");
};

jRequest.send();

/**Handlebars.registerHelper("jiraProjects", function(pName) {
  var iRequest = new XMLHttpRequest();
  iRequest.open('GET', '');
  iRequest.onload = function() {
    if (iRequest.status >= 200 && iRequest.status < 400) {
      var idata = JSON.parse(iRequest.responseText);
      //createIssueTable(idata);
    } else {
      console.log("We connected to the server, but it returned an error for " + pName + ".");
    }
  };
  iRequest.onerror = function() {
     console.log("IssueTemplate Connection error");
  };

  iRequest.send();
});

**/


function createProjectTable(pData) {
  var prawTemplate = document.getElementById("jiraTemplate").innerHTML;
  var pcompiledTemplate = Handlebars.compile(prawTemplate);
  var pGeneratedHTML = pcompiledTemplate(pData);
  var projectContainer = document.getElementById("project-container");
  projectContainer.innerHTML = pGeneratedHTML;
};

function createIssueTable(iData) {
  var irawTemplate = document.getElementById("jiraITemplate").innerHTML;
  var icompiledTemplate = Handlebars.compile(irawTemplate);
  var iGeneratedHTML = icompiledTemplate(iData);
  var issueContainer = document.getElementById("issue-container");
  issueContainer.innerHTML = iGeneratedHTML;
};