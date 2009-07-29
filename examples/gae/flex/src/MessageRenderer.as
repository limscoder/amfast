package {

	import mx.controls.Label;

	public class MessageRenderer extends Label
	{

		override public function set data(value:Object):void
		{
			if(value != null) {
				super.data = value;
				setStyle("color", value.color);
			}
		}
	}
}