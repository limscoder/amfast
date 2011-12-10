package amfastlib.events
{
	import mx.events.FlexEvent;
	
	/**
	 * Dispatched by SaObjects.
	 */
	public class SaEvent extends FlexEvent
	{
		/**
		 * Dispatched when a SaObject is being saved.
		 */
		public static const SAVE:String = 'saEvent_SAVE';
		
		/**
		 * Dispatched after a SaObject has been saved.
		 */
		public static const SAVE_COMPLETE:String = 'saEvent_SAVE_COMPLETE';
		
		/**
		 * Dispatched when a SaObject is removed.
		 */
		public static const REMOVE:String = 'saEvent_REMOVE';
		
		/**
		 * Dispatched after a SaObject has been removed.
		 */
		public static const REMOVE_COMPLETE:String = 'saEvent_REMOVE_COMPLETE';
		
		/**
		 * Dispatched when a SaObject's
		 * persistence status changes.
		 */
		public static const PERSISTENCE_CHANGED:String = 'saEvent_PERSISTENCE_CHANGED';
		
		public function SaEvent(type:String, bubbles:Boolean=false,
			cancelable:Boolean=false)
		{
			super(type, bubbles, cancelable);
		}
	}
}