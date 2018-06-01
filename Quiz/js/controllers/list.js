(function(){
    angular
        .module("educationQuiz")
        .controller("listCtrl", ListController);

		function ListController() {
			var vm = this;
			vm.data = tableData;
		}

		var tableData = [
			{
				question: "What is your current location?",
				answer1: "Las Vegas",
				answer2: "Los Angeles",
				answer3: "Los Alamos",
				answer4: "Las Colinas"
			},
			{
				question: "Why are you doing this project?",
				answer3: "Dunno?",
				answer4: "Achievement?",
				answer1: "To kill some time?",
				answer2: "You got anything better?"
			},
			{
				question: "When is Lunch?",
				answer1: "Morning",
				answer2: "Evening",
				answer3: "Afternoon",
				answer4: "Midnight"
			}
		];

})();