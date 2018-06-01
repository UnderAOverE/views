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
				question: "what?",
				answer1: "a",
				answer2: 1,
				answer3: 3,
				answer4: 4
			},
			{
				question: "why?",
				type: "b",
				answer2: 1,
				answer3: 3,
				answer4: 4
			},
			{
				question: "when?",
				type: "c",
				answer2: 1,
				answer3: 3,
				answer4: 4
			}		
		];
		
})();
