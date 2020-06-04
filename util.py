
class Util:
	def checkQuery(t):
		Util.checkTrue(isinstance(t, list), "query is not a list (" + str(type(t[1])) + ")")
		Util.checkTrue(len(t) == 4, "wrong size of query (" + str(len(t)) + ")")
		Util.checkTrue(isinstance(t[0], list), "coords is not a list (" + str(type(t[1])) + ")")
		Util.checkTrue(isinstance(t[1], date), "from_date has the wrong type (" + str(type(t[1])) + ")")
		Util.checkTrue(isinstance(t[2], date), "till_date has the wrong type (" + str(type(t[1])) + ")")
		Util.checkTrue(t[2] <= date.today(), "till_date cannot be greater than today")
		Util.checkTrue(t[1] < t[2], "from_date must be smaller then till_date")
		Util.checkTrue(isinstance(t[3], float), "max_cloud_coverage has the wrong type (" + str(type(t[1])) + ")")
		Util.checkTrue(t[3] <= 100 and t[3] >= 0, "max_cloud_coverage must be between 0 and 100")

	def checkTrue(a, errorMsg):
		if(not a):
			raise AttributeError(errorMsg)
