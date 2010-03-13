package amfastlib.models
{
	import amfastlib.events.SaAttrEvent;
	import amfastlib.events.SaEvent;
	
	import flash.events.*;
	import flash.utils.*;
	
	import mx.collections.ArrayCollection;
	import mx.collections.ItemResponder;
	import mx.controls.Alert;
	import mx.core.Application;
	import mx.rpc.AsyncToken;
	import mx.rpc.events.*;
	import mx.rpc.remoting.RemoteObject;
	import mx.utils.ObjectUtil;
		
	/**
	 * A base-class for classes mapped with SQLAlchemy on the server side.
	 */
	public class SaObject extends EventDispatcher
	{
		protected const SAVE_ERROR_MSG:String = 'Cannot save un-persisted object.';
		protected const REMOVE_ERROR_MSG:String = 'Cannot remove un-persisted object.';
		protected const LOAD_ATTR_ERROR_MSG:String = 'Cannot load attribute of un-persisted object.';
		protected const SAVE_ATTR_ERROR_MSG:String = 'Cannot save attribute of un-persisted object.';
		
		/**
		 * The names of static attributes of the mapped class.
		 */
		protected static var staticAttrs:Array;
		
		/**
		 * Get an array of attribute
		 * names that are mapped with SA.
		 * 
		 * Unless this method is overridden,
		 * all public attributes and writeable accessors
		 * are considered mapped.
		 * 
		 * The returned Array must contain
		 * 'sa_key' and 'sa_lazy'.
		 */
		public static function getMappedAttrs(obj:*):Array
		{
			if (staticAttrs != null) {
				return staticAttrs;
			}
			
			// Hacky way to introspect for
			// public read/write attributes.
			staticAttrs = [];
			var typeInfo:XML = describeType(obj);
			for each (var accessor:XML in typeInfo..accessor) {
				if (accessor.@access == 'readwrite') {
					staticAttrs.push(accessor.@name);
				}
			}
			
			for each (var attr:XML in typeInfo..variable) {
				staticAttrs.push(attr.@name);
			}
			
			return staticAttrs;
		}
		
		/**
		 * Get the remote alias for a class.
		 */
		public static function getRemoteAlias(obj:*):String
		{
			return ObjectUtil.getClassInfo(obj).alias;
		}
		
		/**
		 * Attributes mapped with SA.
		 */
		[Transient]
		public function get mappedAttrs():Array
		{
			return getMappedAttrs(this);
		}
		
		/**
		 * The remote alias for an object.
		 */
		[Transient]
		public function get remoteAlias():String
		{
			return getRemoteAlias(this);
		}
		
		/**
		 * The service used to perform persistence operations.
		 */
		[Transient]
		public function get service():RemoteObject
		{
			return Application.application.getService();
		}
		
		protected var _sa_key:Array;
		
		/**
		 * Primary key of the persistent object.
		 */
		[Transient]
		public function get sa_key():Array
		{
			return _sa_key;
		}
		
		public function set sa_key(value:Array):void
		{
			if (value != _sa_key) {
				_sa_key = value;
				dispatchEvent(new SaEvent(SaEvent.PERSISTENCE_CHANGED));
			}
		}
		
		/**
		 * Attributes that are lazy-loaded.
		 */
		public var sa_lazy:Array;
		
		/**
		 * Attributes that are in the process
		 * of being loaded from the server.
		 */
		protected var sa_loading:Array;

		/**
		 * Returns true if object is persistent.
		 */
		[Bindable("saEvent_PERSISTENCE_CHANGED")]
		public function get isPersistent():Boolean
		{
			if (_sa_key == null || _sa_key.length < 1 ||
				_sa_key.indexOf(null) > -1) {
				return false;
			}
			
			return true;
		}
		
		/**
		 * Returns true if the attribute
		 * has not been loaded from the database.
		 */
		public function isAttrLazy(attr:String):Boolean
		{
			if (!isPersistent || sa_lazy == null ||
				sa_lazy.indexOf(attr) < 0) {
				return false;
			}
			
			return true;
		}
		
		/**
		 * Sets an attribute so that it is no-longer
		 * considered lazy-loaded.
		 */
		public function setAttr(attr:String, value:*):void
		{
			this[attr] = value;
			
			if (sa_lazy != null) {
				var i:int = sa_lazy.indexOf(attr);
				if (i > -1) {
					sa_lazy.splice(i);
				}
			}
			
			dispatchEvent(new SaAttrEvent(attr, SaAttrEvent.SET));
		}
		
		/**
		 * Sets an attribute to null.
		 * so that it can be lazy-loaded.
		 */
		public function unSetAttr(attr:String):void
		{
			this[attr] = null;
			
			if (sa_lazy == null) {
				sa_lazy = [];
			}
			
			var i:int = sa_lazy.indexOf(attr);
			if (i < 0) {
				sa_lazy.push(attr);
			}
			
			dispatchEvent(new SaAttrEvent(attr, SaAttrEvent.UNSET));
		}
		
		/**
		 * Returns true if the attribute
		 * is being loaded from the server.
		 */
		public function isAttrLoading(attr:String):Boolean
		{
			if (sa_loading == null || sa_loading.indexOf(attr) < 0) {
				return false;
			}
			
			return true;
		}
		
		/**
		 * Sets an attribute so that it is
		 * considered to be loading
		 */
		public function setAttrLoading(attr:String):void
		{
			if (sa_loading == null) {
				sa_loading = [];
			}
			
			var i:int = sa_loading.indexOf(attr);
			if (i < 0) {
				sa_loading.push(attr);
			}
			
			dispatchEvent(new SaAttrEvent(attr, SaAttrEvent.LOAD));
		}
		
		/**
		 * Sets an attribute to not-loading
		 */
		public function unSetAttrLoading(attr:String):void
		{
			if (sa_loading == null) {
				return;
			}
			
			var i:int = sa_loading.indexOf(attr);
			if (i > -1) {
				sa_loading.splice(i);
			}
		}

		/**
		 * Loads a single attribute from the server.
		 */
		public function loadAttr(attr:String):void
		{
			if (!isPersistent) {
				throw new Error(LOAD_ATTR_ERROR_MSG);
			}
			
			/*
			 * Make sure not to call the same
			 * RPC multiple times.
			 */
			if (isAttrLoading(attr)) {
				return;
			}
			
			setAttrLoading(attr);
			var token:AsyncToken = service.loadAttr(remoteAlias, _sa_key, attr);
			token.addResponder(new ItemResponder(loadAttr_resultHandler,
				faultHandler, token));
		}

		/**
		 * Set remotely loaded attribute.
		 */
		protected function loadAttr_resultHandler(event:ResultEvent,
			token:AsyncToken):void
		{
			var attr:String = token.message.body[2];
			setAttr(attr, event.result);
			unSetAttrLoading(attr);
			dispatchEvent(new SaAttrEvent(attr, SaAttrEvent.LOAD_COMPLETE));
		}
		
		/**
		 * Handle a RemoteObject fault.
		 */
		protected function faultHandler(event:FaultEvent,
			token:AsyncToken):void
		{
			throw new Error(String(event.fault.faultString));
		}

		/**
		 * Save a single persistent attribute.
		 */
		public function saveAttr(attr:String):void
		{
			if (!isPersistent) {
				throw new Error(SAVE_ATTR_ERROR_MSG);
			}
			
			dispatchEvent(new SaAttrEvent(attr, SaAttrEvent.SAVE));
			var token:AsyncToken = service.saveAttr(remoteAlias, sa_key, attr, this[attr]);
			token.addResponder(new ItemResponder(saveAttr_resultHandler,
				faultHandler, token));
		}
		
		protected function saveAttr_resultHandler(event:ResultEvent,
			token:AsyncToken):void
		{
			var attr:String = token.message.body[3];
			setAttr(attr, event.result);
			dispatchEvent(new SaAttrEvent(attr, SaAttrEvent.SAVE_COMPLETE));
		}
			
		/**
		 * Persist the entire object.
		 */
		public function save():void
		{
			dispatchEvent(new SaEvent(SaEvent.SAVE));
			var token:AsyncToken = service.save(this);
			token.addResponder(new ItemResponder(save_resultHandler,
				faultHandler, token));
		}
		
		protected function save_resultHandler(event:ResultEvent,
			token:AsyncToken):void
		{
			/*
			 * We have to replace all attributes,
			 * because newly-saved attributes will
			 * now have sa_keys.
			 */
			var saved:SaObject = SaObject(event.result);
			for each(var attr:String in mappedAttrs) {
				if (saved.hasOwnProperty(attr)) {
					this[attr] = saved[attr];
				}
			}
			
			dispatchEvent(new SaEvent(SaEvent.SAVE_COMPLETE));
		}

		/**
		 * Delete persistent object.
		 */
		public function remove():void
		{
			if (!isPersistent) {
				throw new Error(REMOVE_ERROR_MSG);
			}
			
			var token:AsyncToken = service.remove(remoteAlias, sa_key);
			token.addResponder(new ItemResponder(remove_resultHandler,
				faultHandler, token));
		}
		
		protected function remove_resultHandler(event:ResultEvent,
			token:AsyncToken):void
		{
			dispatchEvent(new SaEvent(SaEvent.REMOVE_COMPLETE));
			sa_key = null;
		}
	}
}
