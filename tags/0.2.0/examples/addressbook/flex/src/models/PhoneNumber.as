package models
{
	[RemoteClass(alias="models.PhoneNumber")]	
	[Bindable]
	public class PhoneNumber extends SAObject
	{
		public var id:Object;
		public var user_id:Object;
		public var label:String;
		public var number:String;
	}
}