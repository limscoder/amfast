package models
{
	[RemoteClass(alias="models.PhoneNumber")]	
	[Bindable]
	public class PhoneNumber extends SaObject
	{
		public var id:Object;
		public var user_id:Object;
		public var label:String;
		public var number:String;
	}
}