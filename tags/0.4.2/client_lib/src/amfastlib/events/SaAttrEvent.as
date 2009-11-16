package amfastlib.events
{
	import mx.events.FlexEvent;
	
	/**
	 * Dispatched by SaObjects when an attribute is modified.
	 */
	public class SaAttrEvent extends FlexEvent
	{
		/**
		 * Dispatched when a SaObject attribute is saved.
		 */
		public static const SAVE:String = 'saAttrEvent_SAVE';
		
		/**
		 * Dispatched after a SaObject attribute has been saved.
		 */
		public static const SAVE_COMPLETE:String = 'saAttrEvent_SAVE_COMPLETE';
		
		/**
		 * Dispatched when a SaObject attribute is loaded.
		 */
		public static const LOAD:String = 'saAttrEvent_LOAD';
		
		/**
		 * Dispatched after a SaObject attribute has been loaded.
		 */
		public static const LOAD_COMPLETE:String = 'saAttrEvent_LOAD_COMPLETE';
		
		/**
		 * Dispatched when a SaObject attribute is set.
		 */
		public static const SET:String = 'saAttrEvent_SET';
		
				/**
		 * Dispatched when a SaObject attribute is unset.
		 */
		public static const UNSET:String = 'saAttrEvent_UNSET';
		
		/**
		 * The name of the attribute modified.
		 */
		public var attr:String;
		
		public function SaAttrEvent(attr:String, type:String,
			bubbles:Boolean=false, cancelable:Boolean=false)
		{
			super(type, bubbles, cancelable);
			
			this.attr = attr;
		}
	}
}