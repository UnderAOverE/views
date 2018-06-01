(function(){
    angular
        .module("educationQuiz")
        .controller("listCtrl", ListController);
		
		function ListController($http) {
			var vm = this;
			$http({
					method: 'GET',
					url: 'http://127.0.0.1:8080/data/list.json'
				}).success(function(jsonData) {
					vm.data = jsonData;
				});
		};
})();