package models
{
	import mx.collections.ArrayCollection;
	
	[RemoteClass(alias="models.User")]
	[Bindable]
	public class User extends SAObject
	{
		public var id:Object;
		public var first_name:String;
		public var last_name:String;
		public var emails:ArrayCollection = new ArrayCollection();
		public var phone_numbers:ArrayCollection = new ArrayCollection();
	}
}